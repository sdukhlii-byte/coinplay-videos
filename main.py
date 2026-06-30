"""
main.py — Coinplay Video Generator (Railway cron job).

Сюжетный мультиперсонажный конвейер (story-driven brainrot skit), нативно
продвигающий бренд Coinplay:

  Airtable(Pending)
    → СЦЕНАРИЙ (LLM): идея под вертикаль + каст 2-4 персонажа + диалоги
        + нативный бренд-пейофф + хук
    → РЕФЕРЕНСЫ каста (Nano Banana Pro, параллельно; опц. маскот-камео)
    → по шотам ПАРАЛЛЕЛЬНО: кейфрейм (мульти-референс) + озвучка реплик
        (ElevenLabs, один голос + питч-сдвиги на персонажей)
    → ПАРАЛЛЕЛЬНО анимация шотов (i2v Kling; фолбэк Ken Burns при сбое)
    → субтитры ASS (пословная раскраска по говорящему)
    → ffmpeg-сборка (видео+голос+музыка+сабы+лого+эндкарта)
    → S3/R2 (опц.) → Telegram → Airtable(Done)

Длину i-го шота d_i диктует РЕАЛЬНАЯ длина озвучки этого шота (+хвост),
озвучка в дорожке дополняется тишиной до d_i — так видео/голос/сабы синхронны.

Берём MAX_RECORDS_PER_RUN записей за запуск (видео долгое) — остальное подхватит
следующий крон.
"""

import os
import json
import time
import shutil
import random
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import config as C
from pipeline import clients, script_writer, visuals, voice as voicegen, captions, compose, media
from brand.brand_prompts import MASCOT_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("main")

_job_start = time.monotonic()
def _time_left() -> float:
    return C.MAX_JOB_SECONDS - (time.monotonic() - _job_start)


def _hero_shots() -> set[int]:
    """Опц. HERO_SHOTS="0,4" — какие шоты рендерить hero-моделью (дороже/качественнее)."""
    raw = os.environ.get("HERO_SHOTS", "").strip()
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _pick_music() -> str | None:
    if not os.path.isdir(C.MUSIC_DIR):
        return None
    tracks = [os.path.join(C.MUSIC_DIR, f) for f in os.listdir(C.MUSIC_DIR)
              if f.lower().endswith((".mp3", ".m4a", ".wav"))]
    return random.choice(tracks) if tracks else None


def _field(fields: dict, key: str, default=""):
    return str(fields.get(key, default)).strip()


# ── АНИМАЦИЯ ШОТОВ: параллельно ИЛИ со сцепкой по кадрам ───────────────────────

def _animate_parallel(n: int, keyframes: list, anim_fn) -> list:
    """Текущее поведение: шоты независимы, гоним параллельно."""
    clips = [""] * n

    def _run(i):
        return i, anim_fn(i, keyframes[i])

    with ThreadPoolExecutor(max_workers=max(1, min(C.MAX_PARALLEL_JOBS, n))) as ex:
        for fut in as_completed([ex.submit(_run, i) for i in range(n)]):
            idx, path = fut.result()
            clips[idx] = path
    return clips


def _animate_chained(workdir: str, n: int, keyframes: list, anim_fn) -> list:
    """
    Сцепка по кадрам: первый кадр шота i = ПОСЛЕДНИЙ кадр шота i-1 → бесшовный поток.
    Поэтому строго ПОСЛЕДОВАТЕЛЬНО (i+1 ждёт результат i). Сид-кадр прогоняем через
    visuals._video_frame_url (R2-URL при STORAGE_ENABLED, иначе data-URL).
    """
    clips = [""] * n
    for i in range(n):
        if i > 0 and clips[i - 1]:
            try:
                lf = os.path.join(workdir, f"chain_lf_{i:02d}.png")
                media.extract_last_frame(clips[i - 1], lf)
                seed_url = visuals._video_frame_url(lf)
                keyframes[i] = (seed_url, lf)
                log.info("frame-chain: shot %d seeded from last frame of shot %d", i, i - 1)
            except Exception as e:  # noqa: BLE001
                log.warning("frame-chain: seed for shot %d failed (%s) — using own keyframe",
                            i, str(e)[:120])
        clips[i] = anim_fn(i, keyframes[i])
    return clips


def _animate(workdir: str, n: int, keyframes: list, anim_fn) -> list:
    if C.FRAME_CHAIN:
        return _animate_chained(workdir, n, keyframes, anim_fn)
    return _animate_parallel(n, keyframes, anim_fn)


def _build_video(workdir: str, script: dict, language: str,
                 out_path: str) -> dict:
    """
    Полный рендер ролика из нормализованного сценария. Возвращает метаданные.
    Маршрут зависит от C.VIDEO_ENGINE:
      • veo   — Veo 3.1: персонажи сами говорят (нативное аудио), без TTS;
      • kling — Kling i2v без звука + закадр ElevenLabs + пословные субтитры.
    Вынесено отдельно — переиспользуется в CLI для локального прогона.
    """
    cast = script.get("cast", [])
    shots = script["shots"]
    setting = script.get("setting", "")
    cast_by_id = {m["id"]: m for m in cast}
    n = len(shots)

    log.info("Render[%s]: cast=%d shots=%d lang=%s setting=%r",
             C.VIDEO_ENGINE, len(cast), n, language, setting[:60])

    # ── Фаза 1: референсы каста (параллельно). Общая для обоих маршрутов.
    cast_refs: dict[str, dict] = {}
    if cast:
        cast_refs = visuals.generate_cast(workdir, cast, setting, parallel=True)
        log.info("Cast refs ready: %s", ", ".join(cast_refs.keys()) or "-")
    else:
        log.info("No cast (narrator-only) — keyframes via text-to-image")

    meta_common = {"shots": n, "cast": [m["id"] for m in cast],
                   "has_mascot": MASCOT_ID in cast_by_id}

    if C.VIDEO_ENGINE == "veo":
        return _render_veo(workdir, script, language, shots, cast_by_id,
                           cast_refs, setting, out_path, meta_common)
    return _render_tts(workdir, script, language, shots, cast, cast_by_id,
                       cast_refs, setting, out_path, meta_common)


# ── МАРШРУТ VEO 3.1 (нативное аудио, персонажи сами говорят) ───────────────────

def _render_veo(workdir, script, language, shots, cast_by_id, cast_refs,
                setting, out_path, meta_common) -> dict:
    n = len(shots)

    # Кейфреймы (параллельно) — якорь консистентности персонажей.
    keyframes: list[tuple[str, str]] = [("", "")] * n

    def _do_keyframe(i):
        return i, visuals.generate_keyframe(workdir, i, shots[i], cast_refs, cast_by_id, setting)

    with ThreadPoolExecutor(max_workers=max(1, min(C.MAX_PARALLEL_JOBS, n))) as ex:
        for fut in as_completed([ex.submit(_do_keyframe, i) for i in range(n)]):
            idx, kf = fut.result()
            keyframes[idx] = kf

    # Veo i2v со звуком. Каждый шот = ~8-сек клип, где персонажи говорят.
    # Параллельно (по умолчанию) либо последовательно со сцепкой по кадрам (FRAME_CHAIN).
    def _anim(i, kf):
        kf_url, kf_path = kf
        return visuals.animate_shot(
            workdir, i, kf_url, kf_path, shots[i], target_sec=8.0,
            cast_by_id=cast_by_id, setting=setting, language=language,
        )

    clips = _animate(workdir, n, keyframes, _anim)

    durations = [media.probe_duration(c) for c in clips]

    # Субтитры: в Veo-режиме словных таймкодов нет — максимум хук-текст сверху.
    ass_path = None
    if C.VEO_CAPTIONS != "off" and script.get("on_screen_hook"):
        ass_path = os.path.join(workdir, "subs.ass")
        captions.build_ass([], ass_path, C.VIDEO_W, C.VIDEO_H,
                           font_name=C.FONT_DISPLAY_NAME,
                           on_screen_hook=script["on_screen_hook"], hook_until=2.5)

    music = _pick_music() if C.VEO_MUSIC_UNDER else None
    compose.compose_native(workdir, clips, ass_path, C.LOGO_PATH, music,
                           C.CTA_TEXT, out_path)

    return {"duration": sum(durations), **meta_common}


# ── МАРШРУТ KLING + ELEVENLABS (закадр поверх, пословные субтитры) ─────────────

def _render_tts(workdir, script, language, shots, cast, cast_by_id, cast_refs,
                setting, out_path, meta_common) -> dict:
    n = len(shots)
    # speaker → индекс голосового профиля (narrator=0, маскот=0, прочие=1..4)
    speaker_roles = {"narrator": 0}
    for m in cast:
        speaker_roles[m["id"]] = int(m.get("voice", 0))
    speaker_colors = captions.palette_for([m["id"] for m in cast])

    keyframes: list[tuple[str, str]] = [("", "")] * n
    voices: list[tuple[str, float, list[dict]]] = [("", 0.0, [])] * n

    def _do_keyframe(i):
        return i, visuals.generate_keyframe(workdir, i, shots[i], cast_refs, cast_by_id, setting)

    def _do_voice(i):
        return i, voicegen.synthesize_shot(workdir, i, shots[i].get("dialogue", []),
                                           speaker_roles, language)

    workers = max(1, min(C.MAX_PARALLEL_JOBS, n * 2))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = []
        for i in range(n):
            futs.append(ex.submit(_do_keyframe, i))
            futs.append(ex.submit(_do_voice, i))
        for fut in as_completed(futs):
            res = fut.result()
            idx, payload = res[0], res[1]
            if isinstance(payload, tuple) and len(payload) == 2:
                keyframes[idx] = payload
            else:
                voices[idx] = payload

    durations = [max(voices[i][1] + C.VOICE_TAIL_SEC, C.MIN_SHOT_SEC) for i in range(n)]

    hero = _hero_shots()

    def _anim(i, kf):
        kf_url, kf_path = kf
        return visuals.animate_shot(workdir, i, kf_url, kf_path, shots[i],
                                    durations[i], hero=(i in hero))

    clips = _animate(workdir, n, keyframes, _anim)

    words_global: list[dict] = []
    cursor = 0.0
    for i in range(n):
        for w in voices[i][2]:
            words_global.append({
                "word": w["word"], "start": cursor + w["start"],
                "end": cursor + w["end"], "speaker": w.get("speaker", "narrator"),
            })
        cursor += durations[i]

    ass_path = os.path.join(workdir, "subs.ass")
    captions.build_ass(
        words_global, ass_path, C.VIDEO_W, C.VIDEO_H,
        font_name=C.FONT_DISPLAY_NAME,
        on_screen_hook=script.get("on_screen_hook", ""),
        speaker_colors=speaker_colors,
    )

    voice_tracks = [voices[i][0] for i in range(n)]
    compose.compose(
        workdir, clips, durations, voice_tracks, ass_path,
        logo_path=C.LOGO_PATH, music_path=_pick_music(),
        cta_text=C.CTA_TEXT, out_path=out_path,
    )

    return {"duration": sum(durations), **meta_common}


def process_record(record: dict):
    rid = record["id"]
    fields = record.get("fields", {})

    topic = _field(fields, C.F_TOPIC)
    if not topic:
        log.warning(f"{rid}: empty topic, skip")
        return

    language = (_field(fields, C.F_LANGUAGE) or C.DEFAULT_LANGUAGE).lower()
    vertical = _field(fields, C.F_VERTICAL) or C.DEFAULT_VERTICAL
    fmt      = _field(fields, C.F_FORMAT) or C.DEFAULT_FORMAT
    duration = int(float(_field(fields, C.F_DURATION) or C.DEFAULT_DURATION))
    _default_shots = C.DEFAULT_SHOTS_VEO if C.VIDEO_ENGINE == "veo" else C.DEFAULT_SHOTS
    n_shots  = int(float(_field(fields, C.F_SHOTS) or _default_shots))
    script_override = _field(fields, C.F_SCRIPT_IN)

    log.info("Processing %s: %r lang=%s vertical=%r fmt=%r dur=%ds shots=%d engine=%s",
             rid, topic, language, vertical, fmt, duration, n_shots, C.VIDEO_ENGINE)
    clients.update_record(rid, {C.F_STATUS: C.S_PROGRESS})

    workdir = tempfile.mkdtemp(prefix="cpv_")
    try:
        # 1) Сценарий (или готовый override)
        if script_override:
            script = script_writer.coerce_external(json.loads(script_override))
            log.info("Using Script_Override (coerced): cast=%d shots=%d",
                     len(script.get("cast", [])), len(script["shots"]))
        else:
            script = script_writer.write_script(
                topic, language, n_shots, duration,
                vertical=vertical, fmt=fmt, allow_mascot=C.BRAND_MASCOT_CAMEO,
                spoken=(C.VIDEO_ENGINE == "veo"),
            )

        # 2) Рендер
        out_path = os.path.join(workdir, "output.mp4")
        meta = _build_video(workdir, script, language, out_path)

        # 3) Заливка (если включена) + Telegram + Airtable
        if C.STORAGE_ENABLED:
            key = f"videos/{rid}_{int(time.time())}.mp4"
            video_url = clients.upload_video(out_path, key)
            link_line = f"\n{video_url}"
        else:
            video_url = ""
            link_line = ""
            log.info("Storage disabled — отправляю только в Telegram, Video_URL пустой.")

        cast_line = ", ".join(meta["cast"]) if meta["cast"] else "narrator"
        caption = (f"🎬 *{script.get('title', topic)}*\n"
                   f"Cast: {cast_line}\n"
                   f"Lang: {language}  •  {meta['shots']} shots  •  {meta['duration']:.1f}s{link_line}")
        clients.send_telegram_video(out_path, caption)

        done_fields = {
            C.F_STATUS: C.S_DONE,
            C.F_SCRIPT: json.dumps(script, ensure_ascii=False)[:90000],
        }
        if video_url:
            done_fields[C.F_VIDEO_URL] = video_url
        clients.update_record(rid, done_fields)
        log.info("Done %s%s", rid, (f" → {video_url}" if video_url else " (Telegram only)"))

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
    log.info("Table=%s budget=%ss max_records=%s parallel=%s",
             C.AIRTABLE_TABLE, C.MAX_JOB_SECONDS, C.MAX_RECORDS_PER_RUN, C.MAX_PARALLEL_JOBS)
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
