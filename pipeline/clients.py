"""
pipeline/clients.py — обвязка Airtable / Telegram / S3.
Логика и ретраи скопированы по духу из баннерного main.py, чтобы команде было
знакомо. Здесь же — S3-загрузка видео (замена imgbb).
"""

import os
import time
import logging
import mimetypes

import requests
import boto3
from botocore.config import Config as BotoConfig

import config as C

log = logging.getLogger("clients")


# ── AIRTABLE ───────────────────────────────────────────────────────────────────

def fetch_pending(retries: int = 3) -> list[dict]:
    params = {"filterByFormula": f"{{{C.F_STATUS}}}='{C.S_PENDING}'", "maxRecords": 10}
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(C.AIRTABLE_URL, headers=C.AT_HEADERS, params=params, timeout=15)
            r.raise_for_status()
            records = r.json().get("records", [])
            log.info(f"Fetched {len(records)} pending records")
            return records
        except Exception as e:
            log.warning(f"fetch_pending attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError("fetch_pending failed after all retries")


def update_record(record_id: str, fields: dict, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            r = requests.patch(
                f"{C.AIRTABLE_URL}/{record_id}",
                headers=C.AT_HEADERS, json={"fields": fields}, timeout=15,
            )
            r.raise_for_status()
            return
        except Exception as e:
            log.warning(f"update_record attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    log.error(f"update_record failed for {record_id}")


# ── S3 / R2 (опционально) ──────────────────────────────────────────────────────

_s3 = None
if C.STORAGE_ENABLED:
    _s3 = boto3.client(
        "s3",
        endpoint_url=C.S3_ENDPOINT_URL,
        aws_access_key_id=C.S3_ACCESS_KEY,
        aws_secret_access_key=C.S3_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def upload_video(path: str, key: str) -> str:
    """Заливает файл в бакет, возвращает публичный URL через CDN-домен."""
    if not C.STORAGE_ENABLED:
        raise RuntimeError("Storage disabled (S3_* env vars not set)")
    ctype = mimetypes.guess_type(path)[0] or "video/mp4"
    _s3.upload_file(
        path, C.S3_BUCKET, key,
        ExtraArgs={"ContentType": ctype, "CacheControl": "public, max-age=31536000"},
    )
    url = f"{C.S3_PUBLIC_BASE.rstrip('/')}/{key}"
    log.info(f"Uploaded to S3: {url}")
    return url


# ── TELEGRAM ───────────────────────────────────────────────────────────────────

def send_telegram_video(video_path: str, caption: str, retries: int = 3):
    TG_TIMEOUT = (10, 180)   # видео грузится дольше картинки
    for attempt in range(1, retries + 1):
        try:
            with open(video_path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendVideo",
                    data={
                        "chat_id": C.TELEGRAM_CHAT,
                        "caption": caption[:1024],
                        "parse_mode": "Markdown",
                        "supports_streaming": "true",
                    },
                    files={"video": (os.path.basename(video_path), f, "video/mp4")},
                    timeout=TG_TIMEOUT,
                )
            r.raise_for_status()
            log.info(f"Telegram video sent (attempt {attempt})")
            return
        except Exception as e:
            if attempt < retries:
                log.warning(f"Telegram attempt {attempt}/{retries}: {e} — retry in 5s")
                time.sleep(5)
            else:
                log.warning(f"Telegram failed after {retries} attempts (non-critical): {e}")
