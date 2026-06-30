"""
main.py — Coinplay Video Generator (Railway cron job).

Поток (как в баннерах, но рендер = видео-конвейер):
  Airtable(Pending) → сценарий → персонаж → кейфреймы → i2v клипы →
  закадр ElevenLabs → субтитры ASS → ffmpeg сборка → S3 → Telegram → Done

Берём MAX_RECORDS_PER_RUN записей за запуск (видео долгое). Остальное —
следующий крон подхватит.
"""

import os
import json
import time
import shutil
import random
import logging
import tempfile

import config as C
from pipeline import clients, script_writer, visuals, voice as voicegen, captions, compose

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("main")

_job_start = time.monotonic()
def _time_left() -> float:
    return C.MAX_JOB_SECONDS - (time.monotonic() - _job_start)


def _pick_music() -> str | None:
    if not os.path.isdir(C.MUSIC_DIR):
        return None
    tracks = [os.path.join(C.MUSIC_DIR, f) for f in os.listdir(C.MUSIC_DIR)
              if f.lower().endswith((".mp3", ".m4a", ".wav"))]
    return random.choice(tracks) if tracks else None


def _field(fields: dict, key: str, default=""):
    return str(fields.get(key, default)).strip()


def process_record(record: dict):
    rid = record["id"]
    fields = record.get("fields", {})

    topic = _field(fields, C.F_TOPIC)
    if not topic:
        log.warning(f"{rid}: empty topic, skip")
        return

    language = (_field(fields, C.F_LANGUAGE) or C.DEFAULT_LANGUAGE).lower()
    style    = (_field(fields, C.F_STYLE) or C.DEFAULT_STYLE).lower()
    duration = int(float(_field(fields, C.F_DURATION) or C.DEFAULT_DURATION))
    n_shots  = int(float(_field(fields, C.F_SHOTS) or C.DEFAULT_SHOTS))
    script_override = _field(fields, C.F_SCRIPT_IN)

    log.info(f"Processing {rid}: {topic!r} lang={language} style={style} dur={duration}s shots={n_shots}")
    clients.update_record(rid, {C.F_STATUS: C.S_PROGRESS})

    workdir = tempfile.mkdtemp(prefix="cpv_")
    try:
        # 1) Сценарий
        if script_override:
            script = json.loads(script_override)
        else:
            script = script_writer.write_script(topic, language, n_shots, duration)
        shots = script["shots"]

        # 2) Персонаж (один reference на ролик)
        character_url, _ = visuals.generate_character(workdir)

        # 3) Кейфреймы + 4) анимация + 5) озвучка — по каждому шоту.
        # Озвучку делаем первой: её реальная длина задаёт длину шота d_i.
        clips, durations, voice_mp3s, words_global = [], [], [], []
        cursor = 0.0
        for i, shot in enumerate(shots):
            mp3, vdur, words = voicegen.synthesize(workdir, i, shot["narration"], language)
            d_i = max(vdur + 0.20, 1.5)            # небольшой хвост + минимум
            kf_url, _ = visuals.generate_keyframe(workdir, i, shot, character_url)
            clip = visuals.animate_shot(workdir, i, kf_url, shot, d_i)
            clips.append(clip)
            durations.append(d_i)
            voice_mp3s.append(mp3)
            for w in words:
                if w.get("start") is None or w.get("end") is None:
                    continue
                words_global.append({"word": w["word"],
                                     "start": cursor + w["start"],
                                     "end": cursor + w["end"]})
            cursor += d_i

        # 6) Субтитры
        ass_path = os.path.join(workdir, "subs.ass")
        captions.build_ass(
            words_global, ass_path, C.VIDEO_W, C.VIDEO_H,
            font_name=C.FONT_DISPLAY_NAME, on_screen_hook=script.get("on_screen_hook", ""),
        )

        # 7) Сборка
        out_path = os.path.join(workdir, "output.mp4")
        compose.compose(
            workdir, clips, durations, voice_mp3s, ass_path,
            logo_path=C.LOGO_PATH,
            music_path=_pick_music(),
            cta_text="COINPLAY.COM",
            out_path=out_path,
        )

        # 8) Заливка + Telegram + Airtable
        key = f"videos/{rid}_{int(time.time())}.mp4"
        video_url = clients.upload_video(out_path, key)
        caption = f"🎬 *{script.get('title', topic)}*\nTopic: {topic}\nLang: {language}\n{video_url}"
        clients.send_telegram_video(out_path, caption)
        clients.update_record(rid, {
            C.F_STATUS: C.S_DONE,
            C.F_VIDEO_URL: video_url,
            C.F_SCRIPT: json.dumps(script, ensure_ascii=False)[:90000],
        })
        log.info(f"Done {rid} → {video_url}")

    except Exception as e:
        log.error(f"Failed {rid}: {e}", exc_info=True)
        try:
            clients.update_record(rid, {C.F_STATUS: C.S_ERROR, C.F_ERROR: str(e)[:500]})
        except Exception:
            pass
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    log.info("=== Coinplay Video Generator ===")
    log.info(f"Table={C.AIRTABLE_TABLE} budget={C.MAX_JOB_SECONDS}s max_records={C.MAX_RECORDS_PER_RUN}")
    try:
        records = clients.fetch_pending()
    except Exception as e:
        log.error(f"Cannot fetch records: {e}")
        return
    if not records:
        log.info("No pending records. Exiting.")
        return

    processed = 0
    for record in records:
        if processed >= C.MAX_RECORDS_PER_RUN:
            log.info("Per-run record limit reached, остальное — следующий запуск.")
            break
        if _time_left() < 360:
            log.warning(f"Only {_time_left():.0f}s left (<6min) — stop, leave rest Pending.")
            break
        process_record(record)
        processed += 1

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
