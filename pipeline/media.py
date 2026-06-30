"""
pipeline/media.py — общие обёртки над ffmpeg/ffprobe.
Вынесены отдельно, чтобы и compose, и main пользовались одной реализацией
(раньше _probe_duration жил приватно в compose).
"""

from __future__ import annotations

import json
import logging
import subprocess

log = logging.getLogger("media")


def run_ff(args: list[str], label: str = "") -> None:
    """Запускает ffmpeg, бросает RuntimeError с хвостом stderr при ошибке."""
    log.debug("ffmpeg[%s]: %s ...", label, " ".join(args[:8]))
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg[{label}] failed (rc={proc.returncode}):\n{proc.stderr[-1800:]}")


def probe_duration(path: str) -> float:
    """Длительность медиафайла в секундах (через ffprobe)."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}:\n{proc.stderr[-400:]}")
    return float(json.loads(proc.stdout)["format"]["duration"])
