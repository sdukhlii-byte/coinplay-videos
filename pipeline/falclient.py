"""
pipeline/falclient.py — тонкий клиент очереди fal.ai на requests.

Используем queue API (а не sync), потому что видео-генерация идёт минутами и
синхронный шлюз отвалится по таймауту. Сабмитим → поллим статус → забираем результат.

Док: https://docs.fal.ai/model-endpoints/queue
"""

import time
import logging
import requests

import config as C

log = logging.getLogger("fal")

_QUEUE_BASE = "https://queue.fal.run"
_HEADERS = {"Authorization": f"Key {C.FAL_KEY}", "Content-Type": "application/json"}


def run(model_id: str, payload: dict, poll_interval: float = 4.0,
        timeout: float = 600.0, label: str = "", retries: int = 2) -> dict:
    """
    Запускает модель fal и блокирующе ждёт результат.
    Транзиентные сбои сабмита (429/5xx/сеть) ретраятся с бэкоффом.
    Возвращает JSON-результат модели. Бросает RuntimeError при ошибке/таймауте.
    """
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return _run_once(model_id, payload, poll_interval, timeout, label)
        except RuntimeError as e:
            last_err = e
            # Ретраим только транзиентные классы; явный FAILED модели не ретраим.
            transient = any(s in str(e) for s in ("HTTP 429", "HTTP 5", "timeout", "Connection"))
            if transient and attempt < retries:
                wait = 2 ** attempt
                log.warning("fal[%s] transient (%s), retry %d/%d in %ds",
                            label or model_id, str(e)[:80], attempt, retries, wait)
                time.sleep(wait)
                continue
            raise
    raise last_err  # недостижимо, для типчекера


def _run_once(model_id: str, payload: dict, poll_interval: float,
              timeout: float, label: str) -> dict:
    submit_url = f"{_QUEUE_BASE}/{model_id}"
    r = requests.post(submit_url, headers=_HEADERS, json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"fal submit {model_id} HTTP {r.status_code}: {r.text[:400]}")
    sub = r.json()
    status_url = sub["status_url"]
    response_url = sub["response_url"]
    req_id = sub.get("request_id", "?")
    log.info("fal[%s] submitted req=%s", label or model_id, req_id)

    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"fal[{label or model_id}] timeout after {timeout:.0f}s (req={req_id})")
        time.sleep(poll_interval)
        s = requests.get(status_url, headers=_HEADERS, timeout=30)
        if not s.ok:
            log.warning("fal status HTTP %s: %s", s.status_code, s.text[:200])
            continue
        status = s.json().get("status")
        if status == "COMPLETED":
            break
        if status in ("FAILED", "ERROR", "CANCELED"):
            raise RuntimeError(f"fal[{label or model_id}] status={status}: {s.text[:400]}")
        # IN_QUEUE / IN_PROGRESS → ждём

    res = requests.get(response_url, headers=_HEADERS, timeout=60)
    if not res.ok:
        raise RuntimeError(f"fal result HTTP {res.status_code}: {res.text[:400]}")
    return res.json()


def first_image_url(result: dict) -> str:
    """Достаёт URL картинки из ответа fal-image-модели (форматы разнятся)."""
    if "images" in result and result["images"]:
        return result["images"][0]["url"]
    if "image" in result and isinstance(result["image"], dict):
        return result["image"]["url"]
    raise RuntimeError(f"No image url in fal result: {str(result)[:300]}")


def first_video_url(result: dict) -> str:
    """Достаёт URL видео из ответа fal-video-модели."""
    if "video" in result and isinstance(result["video"], dict):
        return result["video"]["url"]
    if "videos" in result and result["videos"]:
        return result["videos"][0]["url"]
    raise RuntimeError(f"No video url in fal result: {str(result)[:300]}")
