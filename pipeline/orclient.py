"""
pipeline/orclient.py — клиент OpenRouter для картинок и видео.

Зачем: даёт второго провайдера генеративной медиа в дополнение к fal, чтобы
свапнуть весь визуальный слой одной переменной окружения (IMAGE_PROVIDER /
VIDEO_PROVIDER) и не зависеть от блокировок/баланса одного аккаунта.

Две поверхности OpenRouter (обе OpenAI-совместимые по авторизации):
  • Картинки: POST /api/v1/images           — синхронно, ответ base64 (data[].b64_json)
  • Видео:    POST /api/v1/videos (async)     — submit → poll polling_url → скачать unsigned_urls[0]

Доки (сверять при ошибках — API видео молодой и меняется):
  https://openrouter.ai/docs/features/multimodal/image-generation
  https://openrouter.ai/docs/guides/overview/multimodal/video-generation
"""

from __future__ import annotations

import time
import base64
import logging

import requests

import config as C

log = logging.getLogger("or")

_BASE = "https://openrouter.ai/api/v1"


def _headers() -> dict:
    h = {
        "Authorization": f"Bearer {C.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    # Необязательная атрибуция приложения в лидербордах OpenRouter.
    if getattr(C, "OPENROUTER_REFERER", ""):
        h["HTTP-Referer"] = C.OPENROUTER_REFERER
    if getattr(C, "OPENROUTER_TITLE", ""):
        h["X-Title"] = C.OPENROUTER_TITLE
    return h


class ORLocked(RuntimeError):
    """Аккаунт/ключ заблокирован или кончились средства — ретраить бессмысленно."""


class ORBlocked(RuntimeError):
    """
    Запрос отклонён КОНТЕНТ-фильтром модели (Gemini safety / IMAGE_PROHIBITED_CONTENT).
    Ретраить ТЕМ ЖЕ промптом бессмысленно — вызывающий код должен попробовать другой
    (зачищенный) промпт или другую модель. Терминально для данной попытки.
    """


def _raise_for_response(r: requests.Response, what: str) -> None:
    if r.ok:
        return
    body = r.text[:400]
    # 402 = недостаточно кредитов; 403 с упоминанием lock/credit — терминально.
    low = body.lower()
    if r.status_code == 402 or "insufficient" in low or "exhausted" in low or "is locked" in low:
        raise ORLocked(f"OpenRouter {what} HTTP {r.status_code}: {body}")
    # Контент-блок модели (safety). Не ретраим — пусть caller сменит промпт/модель.
    if any(s in low for s in ("prohibited_content", "prohibited", "blocked", "safety",
                              "content policy", "flagged")):
        raise ORBlocked(f"OpenRouter {what} HTTP {r.status_code}: {body}")
    raise RuntimeError(f"OpenRouter {what} HTTP {r.status_code}: {body}")


# ── КАРТИНКИ ───────────────────────────────────────────────────────────────────

def generate_image_bytes(prompt: str, ref_urls: list[str] | None = None,
                         aspect_ratio: str = "9:16", label: str = "",
                         timeout: float = 180.0, retries: int = 3) -> bytes:
    """
    Генерит ОДНУ картинку и возвращает сырые байты (PNG).
    ref_urls — список референс-картинок (http(s) ИЛИ data:-URL) для image-to-image
    (мультиперсонажный кейфрейм). OpenRouter принимает оба варианта в input_references.
    """
    payload: dict = {
        "model": C.OR_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
    }
    if C.OR_IMAGE_RESOLUTION:
        payload["resolution"] = C.OR_IMAGE_RESOLUTION
    if ref_urls:
        payload["input_references"] = [
            {"type": "image_url", "image_url": {"url": u}} for u in ref_urls if u
        ]

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(f"{_BASE}/images", headers=_headers(), json=payload, timeout=timeout)
            _raise_for_response(r, f"image[{label}]")
            data = r.json().get("data") or []
            if not data or not data[0].get("b64_json"):
                raise RuntimeError(f"OpenRouter image[{label}]: no b64_json in {str(r.json())[:300]}")
            log.info("or image[%s] ok (cost=%s)", label or C.OR_IMAGE_MODEL,
                     (r.json().get("usage") or {}).get("cost"))
            return base64.b64decode(data[0]["b64_json"])
        except ORLocked:
            raise  # не ретраим терминальные
        except ORBlocked:
            raise  # контент-блок: ретрай тем же промптом не поможет — наверх
        except (requests.RequestException, RuntimeError) as e:
            last_err = e
            if attempt < retries:
                wait = 2 ** attempt
                log.warning("or image[%s] transient (%s), retry %d/%d in %ds",
                            label, str(e)[:80], attempt, retries, wait)
                time.sleep(wait)
                continue
            raise
    raise last_err  # недостижимо


# ── ВИДЕО (image-to-video) ─────────────────────────────────────────────────────

def _parse_seconds(val) -> int:
    """'8s' / '8' / 8 → 8 (целые секунды; OpenRouter ждёт int)."""
    s = str(val).strip().lower().rstrip("s").strip()
    try:
        return int(round(float(s)))
    except ValueError:
        return 8


def generate_video_bytes(model: str, prompt: str, frame_image_url: str,
                         duration_sec, resolution: str, aspect_ratio: str,
                         generate_audio: bool, label: str = "",
                         timeout: float = 900.0, poll_interval: float = 10.0) -> bytes:
    """
    image-to-video: первый кадр = frame_image_url. Сабмитим джобу, поллим до
    completed, качаем результат. Возвращает сырые байты mp4.

    frame_image_url должен быть ДОСТУПЕН провайдеру: http(s)-URL предпочтительнее.
    data:-URL может прокатить, но не у всех провайдеров — поэтому в visuals.py для
    видео-кадра мы по возможности заливаем кейфрейм в R2 и отдаём публичный URL.
    """
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "duration": _parse_seconds(duration_sec),
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "generate_audio": bool(generate_audio),
        "frame_images": [
            {
                "type": "image_url",
                "image_url": {"url": frame_image_url},
                "frame_type": "first_frame",
            }
        ],
    }

    # Submit
    r = requests.post(f"{_BASE}/videos", headers=_headers(), json=payload, timeout=60)
    _raise_for_response(r, f"video-submit[{label}]")
    sub = r.json()
    job_id = sub.get("id", "?")
    polling_url = sub.get("polling_url") or f"{_BASE}/videos/{job_id}"
    log.info("or video[%s] submitted job=%s status=%s", label or model, job_id, sub.get("status"))

    # Poll
    deadline = time.monotonic() + timeout
    content_url = None
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"OpenRouter video[{label}] timeout after {timeout:.0f}s (job={job_id})")
        time.sleep(poll_interval)
        p = requests.get(polling_url, headers=_headers(), timeout=60)
        if not p.ok:
            # сетевые/временные на поллинге — терпим до дедлайна
            log.warning("or video poll HTTP %s: %s", p.status_code, p.text[:200])
            continue
        js = p.json()
        status = js.get("status")
        if status == "completed":
            urls = js.get("unsigned_urls") or []
            if not urls:
                raise RuntimeError(f"OpenRouter video[{label}] completed but no unsigned_urls")
            content_url = urls[0]
            log.info("or video[%s] completed (cost=%s)", label or model,
                     (js.get("usage") or {}).get("cost"))
            break
        if status in ("failed", "cancelled", "expired"):
            raise RuntimeError(f"OpenRouter video[{label}] {status}: {js.get('error')}")
        # pending / in_progress → ждём

    # Download (контент-URL требует тот же Bearer)
    dl = requests.get(content_url, headers=_headers(), timeout=300)
    if not dl.ok:
        # на части провайдеров unsigned_urls уже подписан и не требует заголовка —
        # пробуем без авторизации.
        dl = requests.get(content_url, timeout=300)
    dl.raise_for_status()
    return dl.content
