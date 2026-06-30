"""
pipeline/visuals.py — картиночно-видео часть (мультиперсонажная).

1) generate_character_ref()  → референс-лист ОДНОГО персонажа (консистентность)
2) generate_cast()           → референсы всех персонажей каста (id → {url, path})
3) generate_keyframe()       → кейфрейм шота из НЕСКОЛЬКИХ референсов (персонажи on-model)
4) animate_shot()            → image-to-video клип из кейфрейма (без аудио),
                               с фолбэком на Ken Burns, если i2v не отдал результат

Все эндпоинты и имена параметров вынесены так, чтобы при смене модели/версии
правки были локальными. Сверяйте поля input с актуальной страницей модели на fal.
"""

from __future__ import annotations

import os
import logging

import requests

import config as C
from pipeline import falclient, media
try:
    from pipeline import orclient            # адаптер OpenRouter (опционален)
except Exception:                            # noqa: BLE001
    orclient = None
from brand.brand_prompts import (
    build_character_ref_prompt, build_mascot_ref_prompt,
    build_keyframe_prompt, build_motion_prompt, MASCOT_ID,
    IMAGE_SAFETY_CLAUSE,
)

log = logging.getLogger("visuals")


def _save(data: bytes, path: str) -> str:
    with open(path, "wb") as f:
        f.write(data)
    return path


def _data_uri(path: str) -> str:
    """Локальный файл → data:-URL (для чейнинга картинок в input_references)."""
    import base64
    import mimetypes
    mt = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mt};base64,{b64}"


def _video_frame_url(path: str) -> str:
    """
    URL первого кадра для OpenRouter video. Публичный http(s)-URL надёжнее всего,
    поэтому при настроенном R2 заливаем кейфрейм и отдаём CDN-ссылку; иначе data:-URL
    (работает не у всех видео-провайдеров — если i2v падает на кадре, включите R2).
    """
    if getattr(C, "STORAGE_ENABLED", False):
        try:
            from pipeline import clients
            key = f"keyframes/{os.path.basename(path)}"
            return clients.upload_video(path, key)
        except Exception as e:  # noqa: BLE001
            log.warning("keyframe upload failed (%s) — fallback to data URI", str(e)[:120])
    return _data_uri(path)


def _download(url: str, dest: str) -> str:
    r = requests.get(url, timeout=120, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    return dest


# ── РЕФЕРЕНС-ЛИСТЫ ПЕРСОНАЖЕЙ ──────────────────────────────────────────────────

def generate_character_ref(workdir: str, member: dict, setting: str = "") -> tuple[str, str]:
    """Референс-лист одного персонажа. Возвращает (ref_url, local_path).

    ref_url — то, что передаётся дальше в кейфрейм как референс:
      • fal        → http(s)-URL результата;
      • openrouter → data:-URL локального файла (OpenRouter принимает data-URL в input_references).
    """
    cid = member.get("id", "char")
    if cid == MASCOT_ID:
        prompt = build_mascot_ref_prompt()
    else:
        prompt = build_character_ref_prompt(member, setting)

    path = os.path.join(workdir, f"ref_{cid}.png")

    if C.IMAGE_PROVIDER == "openrouter":
        if orclient is None:
            raise RuntimeError("IMAGE_PROVIDER=openrouter, но pipeline.orclient не импортировался")
        data = orclient.generate_image_bytes(prompt, aspect_ratio="9:16", label=f"ref:{cid}")
        _save(data, path)
        url = _data_uri(path)
    else:
        payload = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "num_images": 1,
        }
        res = falclient.run(C.MODELS["character_image"], payload, timeout=180, label=f"ref:{cid}")
        url = falclient.first_image_url(res)
        _download(url, path)

    log.info("Character ref ready: %s → %s", cid, path)
    return url, path


def generate_cast(workdir: str, cast: list[dict], setting: str = "",
                  parallel: bool = True) -> dict[str, dict]:
    """
    Генерит референсы всех персонажей каста.
    Возвращает {id: {"url":..., "path":...}}.
    """
    refs: dict[str, dict] = {}
    if not cast:
        return refs

    def _one(member):
        url, path = generate_character_ref(workdir, member, setting)
        return member["id"], {"url": url, "path": path}

    if parallel and len(cast) > 1 and C.MAX_PARALLEL_JOBS > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        workers = min(len(cast), C.MAX_PARALLEL_JOBS)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_one, m): m["id"] for m in cast}
            for fut in as_completed(futs):
                cid, ref = fut.result()
                refs[cid] = ref
    else:
        for m in cast:
            cid, ref = _one(m)
            refs[cid] = ref
    return refs


# ── КЕЙФРЕЙМ ШОТА (мультиреференс) ─────────────────────────────────────────────

def _keyframe_primary(prompt: str, image_urls: list[str], path: str, idx: int) -> str:
    """Одна попытка кейфрейма на ОСНОВНОМ провайдере (с референсами персонажей)."""
    if C.IMAGE_PROVIDER == "openrouter":
        if orclient is None:
            raise RuntimeError("IMAGE_PROVIDER=openrouter, но pipeline.orclient не импортировался")
        data = orclient.generate_image_bytes(
            prompt, ref_urls=image_urls or None, aspect_ratio="9:16", label=f"kf{idx}")
        _save(data, path)
        return _data_uri(path)
    if image_urls:
        payload = {"prompt": prompt, "image_urls": image_urls,   # мульти-референс (edit)
                   "aspect_ratio": "9:16", "num_images": 1}
        model = C.MODELS["keyframe_image"]
    else:
        payload = {"prompt": prompt, "aspect_ratio": "9:16", "num_images": 1}
        model = C.MODELS["character_image"]
    res = falclient.run(model, payload, timeout=180, label=f"kf{idx}")
    url = falclient.first_image_url(res)
    _download(url, path)
    return url


def _keyframe_flux_fallback(prompt: str, path: str, idx: int) -> str:
    """
    Перестраховочный t2i на ПЕРМИССИВНОЙ модели (Flux на fal). Без референсов —
    персонажи могут не совпасть на 100%, НО шот отрисуется и ролик не упадёт.
    Flux на fal принимает image_size (НЕ aspect_ratio), поэтому payload другой.
    Нужен FAL_KEY.
    """
    payload = {"prompt": prompt, "image_size": "portrait_16_9", "num_images": 1}
    res = falclient.run(C.FAL_FALLBACK_IMAGE_MODEL, payload, timeout=180, label=f"kf{idx}-flux")
    url = falclient.first_image_url(res)
    _download(url, path)
    return url


def generate_keyframe(workdir: str, idx: int, shot: dict,
                      cast_refs: dict[str, dict], cast_by_id: dict[str, dict],
                      setting: str = "") -> tuple[str, str]:
    """
    Кейфрейм шота. В edit-модель передаём референсы ВСЕХ персонажей шота, чтобы они
    вышли on-model и в одной сцене.

    Главная причина прежних падений: image-модель (Gemini/Nano Banana) режет кадр как
    IMAGE_PROHIBITED_CONTENT и роняет ВЕСЬ ролик. Теперь — цепочка попыток, чтобы один
    заблокированный кадр не убивал запись:
      1) основная модель, зачищенный промпт (санитайзер уже в build_keyframe_prompt);
      2) она же + явная «чистая» оговорка (fully clothed / non-sexual / no gore)
         — рефы и консистентность персонажей СОХРАНЯЮТСЯ;
      3) пермиссивный Flux (t2i, без рефов) — последний шанс отрисовать шот.
    """
    present = [c for c in (shot.get("characters") or list(cast_by_id.keys()))
               if c in cast_refs]
    image_urls = [cast_refs[c]["url"] for c in present]
    base_prompt = build_keyframe_prompt(shot, cast_by_id, setting)
    path = os.path.join(workdir, f"keyframe_{idx:02d}.png")

    # (label, prompt, use_flux)
    attempts: list[tuple[str, str, bool]] = [
        ("primary",      base_prompt, False),
        ("primary+safe", base_prompt + IMAGE_SAFETY_CLAUSE, False),
    ]
    if getattr(C, "IMAGE_FALLBACK_ENABLED", False):
        attempts.append(("flux-fallback", base_prompt + IMAGE_SAFETY_CLAUSE, True))

    last_err: Exception | None = None
    for label, prompt, use_flux in attempts:
        try:
            if use_flux:
                url = _keyframe_flux_fallback(prompt, path, idx)
                log.info("Keyframe %d ready via FLUX fallback (no refs): %s", idx, path)
            else:
                url = _keyframe_primary(prompt, image_urls, path, idx)
                log.info("Keyframe %d ready (%d refs, %s): %s",
                         idx, len(image_urls), label, path)
            return url, path
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("Keyframe %d attempt '%s' failed (%s)", idx, label, str(e)[:140])
            continue

    raise RuntimeError(f"Keyframe {idx} failed all fallback attempts: {last_err}")


# ── АНИМАЦИЯ ШОТА (image-to-video) ─────────────────────────────────────────────

def _quantize_duration(target_sec: float) -> int:
    """Ближайшая поддерживаемая длина клипа СВЕРХУ (потом обрежем под голос)."""
    allowed = sorted(C.I2V_ALLOWED_DURATIONS)
    for d in allowed:
        if d >= target_sec - 0.25:
            return d
    return allowed[-1]


# ── ВТОРИЧНЫЙ ДВИЖОК (Seedance 1.5 Pro) — фолбэк при отказе Veo ─────────────────

def _animate_seedance(workdir: str, idx: int, keyframe_url: str,
                      keyframe_path: str, prompt: str) -> str:
    """
    Анимация шота вторичным i2v-движком (Seedance 1.5 Pro по умолчанию) с НАТИВНЫМ
    аудио. Зовётся, когда основной движок (Veo) отклонил шот по контент-политике —
    у Seedance фильтр мягче, а звук остаётся внутри клипа (реплики не теряются),
    поэтому результат ложится в compose_native ровно как клип Veo.

    Адаптер параметров (Seedance ≠ Veo!):
      • aspect_ratio — у Seedance дефолт «16:9»; шлём C.VEO_ASPECT («9:16») ЯВНО,
        иначе вертикаль обрежется;
      • duration — СТРОКА секунд (4..12), без суффикса «s»;
      • enable_safety_checker (булев) ВМЕСТО veo-шного safety_tolerance;
      • generate_audio — нативная речь+эмбиент.
    Первый кадр: http(s)-URL предпочтительнее; data-URL fal тоже принимает.
    """
    raw_path = os.path.join(workdir, f"shot_{idx:02d}_raw.mp4")
    frame = keyframe_url if (keyframe_url or "").startswith("http") else _video_frame_url(keyframe_path)
    dur = (C.SECONDARY_DURATION or str(C.VEO_DURATION)).strip().lower().rstrip("s").strip() or "5"

    payload = {
        "prompt": prompt,
        "image_url": frame,
        "aspect_ratio": C.VEO_ASPECT,                 # 9:16 — ЯВНО (дефолт Seedance 16:9)
        "resolution": C.SECONDARY_RESOLUTION,
        "duration": dur,                              # строка секунд
        "generate_audio": bool(C.SECONDARY_GENERATE_AUDIO),
        "enable_safety_checker": bool(C.SECONDARY_SAFETY_CHECKER),
    }
    res = falclient.run(C.SECONDARY_VIDEO_MODEL, payload, timeout=900, label=f"seed{idx}")
    url = falclient.first_video_url(res)
    _download(url, raw_path)
    log.info("Shot %d animated via Seedance (audio=%s, safety_checker=%s): %s",
             idx, C.SECONDARY_GENERATE_AUDIO, C.SECONDARY_SAFETY_CHECKER, raw_path)
    return raw_path


# ── ПОСЛЕДНИЙ ФОЛБЭК: Ken Burns + закадр TTS (не немой) ────────────────────────

def _kenburns_with_tts(workdir: str, idx: int, keyframe_path: str, shot: dict,
                       target_sec: float, cast_by_id: dict | None,
                       language: str) -> str:
    """
    Статичный клип из кейфрейма (Ken Burns) + озвучка реплик шота через ElevenLabs,
    чтобы шот не уходил немым. Длину диктует длина озвучки (+хвост). Если KENBURNS_TTS
    выключен, реплик нет или TTS упал — обычный немой Ken Burns (как раньше).
    """
    raw_path = os.path.join(workdir, f"shot_{idx:02d}_raw.mp4")
    dialogue = [d for d in (shot.get("dialogue") or []) if str(d.get("line", "")).strip()]

    if not getattr(C, "KENBURNS_TTS", False) or not dialogue:
        media.ken_burns_clip(keyframe_path, raw_path, max(target_sec, C.MIN_SHOT_SEC),
                             C.VIDEO_W, C.VIDEO_H, C.FPS)
        return raw_path

    try:
        from pipeline import voice as voicegen     # ленивый импорт (как и orclient)
        speaker_roles = {"narrator": 0}
        for cid, m in (cast_by_id or {}).items():
            speaker_roles[cid] = int(m.get("voice", 0))
        voice_wav, vdur, _ = voicegen.synthesize_shot(
            workdir, idx, dialogue, speaker_roles, language)
        clip_dur = max(vdur + C.VOICE_TAIL_SEC, C.MIN_SHOT_SEC)
        silent = os.path.join(workdir, f"shot_{idx:02d}_kb_silent.mp4")
        media.ken_burns_clip(keyframe_path, silent, clip_dur,
                             C.VIDEO_W, C.VIDEO_H, C.FPS)
        media.mux_audio(silent, voice_wav, raw_path, clip_dur)
        log.info("Shot %d Ken Burns + TTS voiceover (%.2fs, %d lines): %s",
                 idx, clip_dur, len(dialogue), raw_path)
        return raw_path
    except Exception as e:  # noqa: BLE001
        log.warning("Shot %d Ken Burns TTS failed (%s) — silent Ken Burns",
                    idx, str(e)[:120])
        media.ken_burns_clip(keyframe_path, raw_path, max(target_sec, C.MIN_SHOT_SEC),
                             C.VIDEO_W, C.VIDEO_H, C.FPS)
        return raw_path


def animate_shot(workdir: str, idx: int, keyframe_url: str, keyframe_path: str,
                 shot: dict, target_sec: float, hero: bool = False,
                 cast_by_id: dict | None = None, setting: str = "",
                 language: str = "en") -> str:
    """
    Создаёт видеоклип шота, возвращает local_path.

    Режим C.VIDEO_ENGINE:
      • veo   — Veo 3.1 i2v с НАТИВНЫМ аудио: персонажи сами проговаривают реплики
                (липсинк + эмбиент). Звук уже ВНУТРИ клипа, отдельный TTS не нужен.
      • kling — Kling i2v без звука (голос кладётся отдельно через ElevenLabs).

    При сбое i2v и включённом фолбэке собираем немой клип из кейфрейма (Ken Burns).
    """
    raw_path = os.path.join(workdir, f"shot_{idx:02d}_raw.mp4")

    if C.VIDEO_ENGINE == "veo":
        from brand.brand_prompts import build_veo_prompt
        prompt = build_veo_prompt(shot, cast_by_id or {}, setting, language)
        try:
            if C.VIDEO_PROVIDER == "openrouter":
                if orclient is None:
                    raise RuntimeError("VIDEO_PROVIDER=openrouter, но pipeline.orclient не импортировался")
                frame_url = _video_frame_url(keyframe_path)
                data = orclient.generate_video_bytes(
                    model=C.OR_VIDEO_MODEL_VEO, prompt=prompt, frame_image_url=frame_url,
                    duration_sec=C.VEO_DURATION, resolution=C.VEO_RESOLUTION,
                    aspect_ratio=C.VEO_ASPECT, generate_audio=C.VEO_GENERATE_AUDIO,
                    label=f"veo{idx}", timeout=900)
                _save(data, raw_path)
                log.info("Shot %d animated via Veo/OpenRouter (audio=%s): %s",
                         idx, C.VEO_GENERATE_AUDIO, raw_path)
            else:
                model = C.veo_i2v_model()
                payload = {
                    "prompt": prompt,
                    "image_url": keyframe_url,                # Veo i2v берёт ОДНУ картинку
                    "aspect_ratio": C.VEO_ASPECT,
                    "duration": C.VEO_DURATION,               # строка "8s"/"6s"/"4s"
                    "resolution": C.VEO_RESOLUTION,
                    "generate_audio": C.VEO_GENERATE_AUDIO,   # ← модель сама говорит
                    "negative_prompt": C.I2V_NEGATIVE,
                    "safety_tolerance": C.VEO_SAFETY,
                }
                res = falclient.run(model, payload, timeout=900, label=f"veo{idx}")
                url = falclient.first_video_url(res)
                _download(url, raw_path)
                log.info("Shot %d animated via Veo (%s, audio=%s): %s",
                         idx, C.VEO_TIER, C.VEO_GENERATE_AUDIO, raw_path)
            return raw_path
        except Exception as e:
            log.warning("Shot %d Veo failed (%s)", idx, str(e)[:140])
            # ── ЦЕПОЧКА ФОЛБЭКА ────────────────────────────────────────────────
            # 1) Вторичный движок (Seedance): мягче фильтр + нативное аудио, поэтому
            #    реплики НЕ теряются, а результат ложится в compose_native как Veo-клип.
            if getattr(C, "SECONDARY_VIDEO_ENABLED", False):
                try:
                    return _animate_seedance(workdir, idx, keyframe_url, keyframe_path, prompt)
                except Exception as e2:  # noqa: BLE001
                    log.warning("Shot %d Seedance fallback failed (%s)", idx, str(e2)[:140])
            # 2) Последний фолбэк: Ken Burns + закадр TTS (чтобы не был немым).
            if not C.I2V_FALLBACK_KENBURNS:
                raise
            return _kenburns_with_tts(workdir, idx, keyframe_path, shot,
                                      target_sec, cast_by_id, language)

    # ── kling (или иной) i2v без звука ──────────────────────────────────────────
    dur = _quantize_duration(target_sec)
    prompt = build_motion_prompt(shot)
    try:
        if C.VIDEO_PROVIDER == "openrouter":
            if orclient is None:
                raise RuntimeError("VIDEO_PROVIDER=openrouter, но pipeline.orclient не импортировался")
            frame_url = _video_frame_url(keyframe_path)
            data = orclient.generate_video_bytes(
                model=C.OR_VIDEO_MODEL_I2V, prompt=prompt, frame_image_url=frame_url,
                duration_sec=dur, resolution=C.I2V_RESOLUTION, aspect_ratio=C.VEO_ASPECT,
                generate_audio=False, label=f"i2v{idx}", timeout=600)
            _save(data, raw_path)
            log.info("Shot %d animated via i2v/OpenRouter (%ds): %s", idx, dur, raw_path)
        else:
            model = C.MODELS["image_to_video_hero"] if hero else C.MODELS["image_to_video"]
            payload = {
                "prompt": prompt,
                "image_url": keyframe_url,
                "duration": str(dur),          # Kling ждёт строку "5"/"10"; для иных моделей — int
                "resolution": C.I2V_RESOLUTION,
                "negative_prompt": C.I2V_NEGATIVE,
                "generate_audio": False,
            }
            res = falclient.run(model, payload, timeout=600, label=f"i2v{idx}")
            url = falclient.first_video_url(res)
            _download(url, raw_path)
            log.info("Shot %d animated (%ds requested → fit %.2fs later): %s",
                     idx, dur, target_sec, raw_path)
        return raw_path
    except Exception as e:
        if not C.I2V_FALLBACK_KENBURNS:
            raise
        log.warning("Shot %d i2v failed (%s) — falling back to Ken Burns from keyframe",
                    idx, str(e)[:140])
        media.ken_burns_clip(keyframe_path, raw_path, max(target_sec, C.MIN_SHOT_SEC),
                             C.VIDEO_W, C.VIDEO_H, C.FPS)
        return raw_path
