"""
pipeline/voice.py — закадровый голос через ElevenLabs (с таймкодами).

Отличие от MVP: шот теперь может содержать НЕСКОЛЬКО реплик разных персонажей
(формат «фрукты спорят»). Поэтому:
  • каждую реплику синтезируем своим голосом (профиль роли: voice_id + pitch),
  • разные персонажи звучат по-разному даже из ОДНОГО голоса — через сдвиг тона,
  • реплики склеиваются с короткими паузами в единую дорожку шота,
  • пословные тайминги сшиваются в общий таймлайн шота и тегируются спикером
    (это даёт цветные «по говорящему» brainrot-субтитры).

Endpoint with-timestamps возвращает аудио + посимвольные тайминги; из них
собираем пословные тайминги. Длительность дорожки шота меряем ffprobe'ом —
она задаёт длину шота d_i (инвариант синхрона голос↔видео↔субтитры).

Док: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
"""

from __future__ import annotations

import os
import time
import base64
import logging

import requests

import config as C
from pipeline import media

log = logging.getLogger("voice")


# ── РАЗБОР ТАЙМКОДОВ ───────────────────────────────────────────────────────────

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


# ── СИНТЕЗ ОДНОЙ РЕПЛИКИ ───────────────────────────────────────────────────────

def _synthesize_line(workdir: str, tag: str, text: str, profile: dict,
                     retries: int = 3) -> tuple[str, float, list[dict]]:
    """
    Озвучивает одну реплику профилем `profile` ({voice_id, pitch, style}).
    Возвращает (wav_path, duration, words[]) с таймингами относительно реплики.
    Сдвиг тона (если pitch!=0) сохраняет длительность → тайминги остаются валидны.
    """
    voice_id = profile["voice_id"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"xi-api-key": C.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": C.ELEVEN_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": float(profile.get("style", C.ELEVEN_STYLE)),
        },
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
            mp3_path = os.path.join(workdir, f"line_{tag}.mp3")
            with open(mp3_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))

            alignment = data.get("alignment") or data.get("normalized_alignment") or {}
            words = _words_from_alignment(alignment)

            # mp3 → wav (+ сдвиг тона по профилю; pitch=0 просто перекодирует).
            wav_path = os.path.join(workdir, f"line_{tag}.wav")
            media.pitch_shift(mp3_path, wav_path, profile.get("pitch", 0.0))

            duration = media.probe_duration(wav_path)
            # хвост последнего слова не должен превышать реальную длину файла
            if words and words[-1]["end"] > duration:
                duration = words[-1]["end"]
            log.info("Line %s: %.2fs, %d words, pitch=%+.1f",
                     tag, duration, len(words), profile.get("pitch", 0.0))
            return wav_path, duration, words

        except Exception as e:
            last_err = e
            if attempt < retries:
                wait = 2 ** attempt
                log.warning("synth line %s attempt %d/%d: %s — retry in %ds",
                            tag, attempt, retries, str(e)[:120], wait)
                time.sleep(wait)
    raise RuntimeError(f"synth line {tag} failed after {retries} attempts: {last_err}")


# ── СКЛЕЙКА WAV-ОВ ─────────────────────────────────────────────────────────────

def _concat_wavs(paths: list[str], dst: str) -> str:
    """Склейка нескольких wav через concat-фильтр (надёжно для разнородных wav)."""
    if len(paths) == 1:
        # просто нормализуем в нужный формат
        media.run_ff(["ffmpeg", "-y", "-i", paths[0], "-ar", "44100", "-ac", "2", dst],
                     label="voice_copy")
        return dst
    inputs: list[str] = []
    for p in paths:
        inputs += ["-i", p]
    n = len(paths)
    fc = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    media.run_ff([
        "ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[a]",
        "-ar", "44100", "-ac", "2", dst,
    ], label="voice_concat")
    return dst


# ── СИНТЕЗ ДОРОЖКИ ШОТА (несколько реплик) ─────────────────────────────────────

def synthesize_shot(workdir: str, shot_idx: int, dialogue: list[dict],
                    speaker_roles: dict[str, int], language: str
                    ) -> tuple[str, float, list[dict]]:
    """
    Озвучивает ВЕСЬ шот: список реплик [{speaker, line}].
      speaker_roles: speaker(id|'narrator') → индекс голосового профиля (0..4)
    Возвращает (wav_path, duration, words[]), где words = [{word,start,end,speaker}]
    в таймлайне ЭТОГО шота (от 0). Пустой dialogue → «немой» бит тишины.
    """
    dialogue = [d for d in (dialogue or []) if str(d.get("line", "")).strip()]

    # Немой бит (пауза перед панчлайном и т.п.)
    if not dialogue:
        wav = os.path.join(workdir, f"voice_{shot_idx:02d}.wav")
        media.make_silence(wav, C.SILENT_BEAT_SEC)
        log.info("Shot %d: silent beat %.2fs", shot_idx, C.SILENT_BEAT_SEC)
        return wav, C.SILENT_BEAT_SEC, []

    seg_paths: list[str] = []
    words_global: list[dict] = []
    cursor = 0.0
    gap = max(C.VOICE_GAP_SEC, 0.0)
    gap_wav = None
    if gap > 0 and len(dialogue) > 1:
        gap_wav = os.path.join(workdir, f"_gap_{shot_idx:02d}.wav")
        media.make_silence(gap_wav, gap)

    for li, line in enumerate(dialogue):
        speaker = str(line.get("speaker", "narrator")).strip() or "narrator"
        role = speaker_roles.get(speaker, 0)
        profile = C.voice_profile(role, language)
        tag = f"{shot_idx:02d}_{li:02d}"
        wav, dur, words = _synthesize_line(workdir, tag, line["line"].strip(), profile)

        for w in words:
            if w.get("start") is None or w.get("end") is None:
                continue
            words_global.append({
                "word": w["word"],
                "start": cursor + w["start"],
                "end": cursor + w["end"],
                "speaker": speaker,
            })
        seg_paths.append(wav)
        cursor += dur

        if gap_wav and li < len(dialogue) - 1:
            seg_paths.append(gap_wav)
            cursor += gap

    shot_wav = os.path.join(workdir, f"voice_{shot_idx:02d}.wav")
    _concat_wavs(seg_paths, shot_wav)
    duration = media.probe_duration(shot_wav)
    log.info("Shot %d voice: %.2fs, %d lines, %d words",
             shot_idx, duration, len(dialogue), len(words_global))
    return shot_wav, duration, words_global
