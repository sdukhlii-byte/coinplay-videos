"""
pipeline/voice.py — закадровый голос через ElevenLabs (с таймкодами).

Endpoint with-timestamps возвращает аудио + посимвольные тайминги; из них
собираем пословные тайминги для синхронных «brainrot»-субтитров.

Возвращаемая длительность = max(конец последнего слова, реальная длина файла),
чтобы паддинг шота гарантированно не обрезал хвост речи.

Док: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
"""

from __future__ import annotations

import os
import time
import base64
import logging

import requests

import config as C
from pipeline.media import probe_duration

log = logging.getLogger("voice")


def _words_from_alignment(alignment: dict) -> list[dict]:
    """Группирует посимвольные тайминги в слова по пробелам."""
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    words: list[dict] = []
    cur, w_start, w_end = "", None, None
    for ch, st, en in zip(chars, starts, ends):
        if ch.isspace():
            if cur and w_start is not None:
                words.append({"word": cur, "start": w_start, "end": w_end})
            cur, w_start, w_end = "", None, None
        else:
            if not cur:
                w_start = st
            cur += ch
            w_end = en
    if cur and w_start is not None:
        words.append({"word": cur, "start": w_start, "end": w_end})
    return words


def synthesize(workdir: str, idx: int, text: str, language: str,
               retries: int = 3) -> tuple[str, float, list[dict]]:
    """
    Озвучивает строку шота. Возвращает (mp3_path, duration_sec, words[]),
    где words = [{word, start, end}] относительно начала ЭТОГО клипа.
    """
    voice_id = C.voice_for(language)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"xi-api-key": C.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": C.ELEVEN_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3},
    }

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()

            audio_b64 = data.get("audio_base64") or data.get("audio")
            if not audio_b64:
                raise RuntimeError(f"No audio in ElevenLabs response: {str(data)[:200]}")
            mp3_path = os.path.join(workdir, f"voice_{idx:02d}.mp3")
            with open(mp3_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))

            alignment = data.get("alignment") or data.get("normalized_alignment") or {}
            words = _words_from_alignment(alignment)
            words_end = words[-1]["end"] if words else 0.0
            duration = max(words_end, probe_duration(mp3_path))
            log.info("Voice %d: %.2fs, %d words", idx, duration, len(words))
            return mp3_path, duration, words

        except Exception as e:
            last_err = e
            if attempt < retries:
                wait = 2 ** attempt
                log.warning("synthesize attempt %d/%d: %s — retry in %ds",
                            attempt, retries, str(e)[:120], wait)
                time.sleep(wait)
    raise RuntimeError(f"synthesize failed after {retries} attempts: {last_err}")
