"""
pipeline/voice.py — закадровый голос через ElevenLabs (с таймкодами).

Используем endpoint with-timestamps: возвращает аудио + посимвольные тайминги.
Из них собираем пословные тайминги для синхронных «brainrot»-субтитров.

Док: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
"""

import os
import base64
import logging

import requests

import config as C

log = logging.getLogger("voice")


def _words_from_alignment(alignment: dict) -> list[dict]:
    """Группирует посимвольные тайминги в слова по пробелам."""
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    words, cur, w_start, w_end = [], "", None, None
    for ch, st, en in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": w_start, "end": w_end})
                cur, w_start, w_end = "", None, None
        else:
            if not cur:
                w_start = st
            cur += ch
            w_end = en
    if cur:
        words.append({"word": cur, "start": w_start, "end": w_end})
    return words


def synthesize(workdir: str, idx: int, text: str, language: str) -> tuple[str, float, list[dict]]:
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
    duration = words[-1]["end"] if words else 0.0
    log.info(f"Voice {idx}: {duration:.2f}s, {len(words)} words")
    return mp3_path, duration, words
