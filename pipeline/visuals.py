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
from brand.brand_prompts import (
    build_character_ref_prompt, build_mascot_ref_prompt,
    build_keyframe_prompt, build_motion_prompt, MASCOT_ID,
)

log = logging.getLogger("visuals")


def _download(url: str, dest: str) -> str:
    r = requests.get(url, timeout=120, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    return dest


# ── РЕФЕРЕНС-ЛИСТЫ ПЕРСОНАЖЕЙ ──────────────────────────────────────────────────

def generate_character_ref(workdir: str, member: dict, setting: str = "") -> tuple[str, str]:
    """Референс-лист одного персонажа. Возвращает (url, local_path)."""
    cid = member.get("id", "char")
    if cid == MASCOT_ID:
        prompt = build_mascot_ref_prompt()
    else:
        prompt = build_character_ref_prompt(member, setting)
    payload = {
        "prompt": prompt,
        "aspect_ratio": "9:16",
        "num_images": 1,
    }
    res = falclient.run(C.MODELS["character_image"], payload, timeout=180, label=f"ref:{cid}")
    url = falclient.first_image_url(res)
    path = _download(url, os.path.join(workdir, f"ref_{cid}.png"))
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

def generate_keyframe(workdir: str, idx: int, shot: dict,
                      cast_refs: dict[str, dict], cast_by_id: dict[str, dict],
                      setting: str = "") -> tuple[str, str]:
    """
    Кейфрейм шота. В edit-модель передаём референсы ВСЕХ персонажей, которые в шоте,
    чтобы они вышли on-model и в одной сцене.
    """
    present = [c for c in (shot.get("characters") or list(cast_by_id.keys()))
               if c in cast_refs]
    image_urls = [cast_refs[c]["url"] for c in present]
    prompt = build_keyframe_prompt(shot, cast_by_id, setting)

    if image_urls:
        payload = {
            "prompt": prompt,
            "image_urls": image_urls,     # мульти-референс (edit-режим Nano Banana Pro)
            "aspect_ratio": "9:16",
            "num_images": 1,
        }
        model = C.MODELS["keyframe_image"]
    else:
        # нет персонажей (вырожденный случай / legacy) → чистый text-to-image
        payload = {"prompt": prompt, "aspect_ratio": "9:16", "num_images": 1}
        model = C.MODELS["character_image"]

    res = falclient.run(model, payload, timeout=180, label=f"kf{idx}")
    url = falclient.first_image_url(res)
    path = _download(url, os.path.join(workdir, f"keyframe_{idx:02d}.png"))
    log.info("Keyframe %d ready (%d refs): %s", idx, len(image_urls), path)
    return url, path


# ── АНИМАЦИЯ ШОТА (image-to-video) ─────────────────────────────────────────────

def _quantize_duration(target_sec: float) -> int:
    """Ближайшая поддерживаемая длина клипа СВЕРХУ (потом обрежем под голос)."""
    allowed = sorted(C.I2V_ALLOWED_DURATIONS)
    for d in allowed:
        if d >= target_sec - 0.25:
            return d
    return allowed[-1]


def animate_shot(workdir: str, idx: int, keyframe_url: str, keyframe_path: str,
                 shot: dict, target_sec: float, hero: bool = False) -> str:
    """
    Создаёт видеоклип шота, возвращает local_path. Аудио НЕ генерим (свой голос).
    Если i2v падает (таймаут/ошибка модели) и включён фолбэк — собираем клип
    из кейфрейма (Ken Burns), чтобы ролик всё равно достроился.
    """
    model = C.MODELS["image_to_video_hero"] if hero else C.MODELS["image_to_video"]
    dur = _quantize_duration(target_sec)
    payload = {
        "prompt": build_motion_prompt(shot),
        "image_url": keyframe_url,
        "duration": str(dur),          # Kling ждёт строку "5"/"10"; для иных моделей — int
        "resolution": C.I2V_RESOLUTION,
        "negative_prompt": C.I2V_NEGATIVE,
        "generate_audio": False,
    }
    try:
        res = falclient.run(model, payload, timeout=600, label=f"i2v{idx}")
        url = falclient.first_video_url(res)
        path = _download(url, os.path.join(workdir, f"shot_{idx:02d}_raw.mp4"))
        log.info("Shot %d animated (%ds requested → fit %.2fs later): %s",
                 idx, dur, target_sec, path)
        return path
    except Exception as e:
        if not C.I2V_FALLBACK_KENBURNS:
            raise
        log.warning("Shot %d i2v failed (%s) — falling back to Ken Burns from keyframe",
                    idx, str(e)[:140])
        path = os.path.join(workdir, f"shot_{idx:02d}_raw.mp4")
        media.ken_burns_clip(keyframe_path, path, max(target_sec, C.MIN_SHOT_SEC),
                             C.VIDEO_W, C.VIDEO_H, C.FPS)
        return path
