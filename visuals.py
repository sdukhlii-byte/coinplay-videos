"""
pipeline/visuals.py — картиночно-видео часть.

1) generate_character()  → одно reference-изображение маскота (консистентность)
2) generate_keyframe()   → кейфрейм шота, с передачей reference для on-model персонажа
3) animate_shot()        → image-to-video клип из кейфрейма (Kling v3 Pro, без аудио)

Все эндпоинты и имена параметров вынесены так, чтобы при смене модели/версии
правки были локальными. Сверяйте поля input с актуальной страницей модели на fal.
"""

import os
import math
import logging

import requests

import config as C
from pipeline import falclient
from brand.brand_prompts import (
    build_character_prompt, build_keyframe_prompt, build_motion_prompt,
)

log = logging.getLogger("visuals")


def _download(url: str, dest: str) -> str:
    r = requests.get(url, timeout=120, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    return dest


# ── ПЕРСОНАЖ ───────────────────────────────────────────────────────────────────

def generate_character(workdir: str) -> tuple[str, str]:
    """Возвращает (url, local_path) reference-изображения персонажа."""
    payload = {
        "prompt": build_character_prompt(),
        # Имена полей под Nano Banana Pro; при иной модели — поправьте здесь.
        "aspect_ratio": "9:16",
        "num_images": 1,
    }
    res = falclient.run(C.MODELS["character_image"], payload, timeout=180, label="character")
    url = falclient.first_image_url(res)
    path = _download(url, os.path.join(workdir, "character_ref.png"))
    log.info(f"Character reference ready: {path}")
    return url, path


# ── КЕЙФРЕЙМ ШОТА ──────────────────────────────────────────────────────────────

def generate_keyframe(workdir: str, idx: int, shot: dict, character_url: str) -> tuple[str, str]:
    payload = {
        "prompt": build_keyframe_prompt(shot["visual"], shot.get("mood", "")),
        "image_urls": [character_url],   # reference для консистентности (edit-режим)
        "aspect_ratio": "9:16",
        "num_images": 1,
    }
    res = falclient.run(C.MODELS["keyframe_image"], payload, timeout=180, label=f"keyframe{idx}")
    url = falclient.first_image_url(res)
    path = _download(url, os.path.join(workdir, f"keyframe_{idx:02d}.png"))
    log.info(f"Keyframe {idx} ready: {path}")
    return url, path


# ── АНИМАЦИЯ ШОТА (image-to-video) ─────────────────────────────────────────────

def _quantize_duration(target_sec: float) -> int:
    """Ближайшая поддерживаемая длина клипа СВЕРХУ (чтобы потом обрезать под голос)."""
    allowed = sorted(C.I2V_ALLOWED_DURATIONS)
    for d in allowed:
        if d >= target_sec - 0.25:
            return d
    return allowed[-1]


def animate_shot(workdir: str, idx: int, keyframe_url: str, shot: dict,
                 target_sec: float, hero: bool = False) -> str:
    """Создаёт видеоклип шота, возвращает local_path. Аудио НЕ генерим (свой голос)."""
    model = C.MODELS["image_to_video_hero"] if hero else C.MODELS["image_to_video"]
    dur = _quantize_duration(target_sec)
    payload = {
        "prompt": build_motion_prompt(shot.get("motion", "")),
        "image_url": keyframe_url,
        "duration": str(dur),          # Kling ждёт строку "5"/"10"; для иных моделей — int
        "resolution": C.I2V_RESOLUTION,
        "generate_audio": False,
    }
    res = falclient.run(model, payload, timeout=600, label=f"i2v{idx}")
    url = falclient.first_video_url(res)
    path = _download(url, os.path.join(workdir, f"shot_{idx:02d}_raw.mp4"))
    log.info(f"Shot {idx} animated ({dur}s requested → fit {target_sec:.2f}s later): {path}")
    return path
