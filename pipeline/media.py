"""
pipeline/media.py — общие обёртки над ffmpeg/ffprobe + низкоуровневые медиа-операции.

Здесь живут переиспользуемые кирпичи, которыми пользуются и compose, и voice, и main:
  • run_ff / probe_duration   — запуск ffmpeg и измерение длины
  • make_silence              — wav-тишина заданной длины
  • pitch_shift               — сдвиг высоты тона БЕЗ изменения длительности
                                (так из одного голоса делаем разных «персонажей»)
  • concat_demux              — склейка однотипных медиа через concat-демуксер
  • ken_burns_clip            — клип из статичной картинки (медленный зум) —
                                фолбэк, если image-to-video упал
"""

from __future__ import annotations

import os
import json
import math
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


def estimate_speech_sec(dialogue: list | None, wps: float = 2.3) -> float:
    """
    Грубая оценка длительности речи шота по тексту реплик (сек). 0 = молчаливый шот.
    Общий источник правды для (а) обрезки хвостов в compose и (б) выбора длины
    Veo-клипа на сабмите — чтобы они не расходились.
    """
    words = lines = 0
    for d in (dialogue or []):
        t = str(d.get("line", "")).strip()
        if t:
            words += len(t.split())
            lines += 1
    if not words:
        return 0.0
    return words / max(1.5, wps) + lines * 0.35


def has_audio(path: str) -> bool:
    """True, если в файле есть хотя бы одна аудиодорожка."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def mux_audio(video_src: str, audio_src: str, dst: str, duration: float) -> str:
    """
    Накладывает аудиодорожку (wav) на видео БЕЗ звука и режет результат до `duration`.
    Аудио дополняется тишиной (apad) и обрезается под длину видео, видеопоток
    копируется без реэнкода. Используется для фолбэка «Ken Burns + закадр TTS»,
    чтобы статичный клип не уходил немым.
    """
    run_ff([
        "ffmpeg", "-y", "-i", video_src, "-i", audio_src,
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", "apad", "-t", f"{duration:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", dst,
    ], label="mux_audio")
    return dst


# ── АУДИО-КИРПИЧИ ──────────────────────────────────────────────────────────────

def make_silence(dst: str, duration: float, sr: int = 44100) -> str:
    """Стерео-wav тишины заданной длины."""
    run_ff([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r={sr}:cl=stereo", "-t", f"{max(duration, 0.01):.3f}",
        "-ar", str(sr), "-ac", "2", dst,
    ], label="silence")
    return dst


def _atempo_chain(factor: float) -> str:
    """
    ffmpeg atempo принимает 0.5..2.0 за один проход. Для больших коэффициентов
    раскладываем в цепочку. factor — во сколько раз менять ТЕМП.
    """
    if abs(factor - 1.0) < 1e-3:
        return "atempo=1.0"
    steps = []
    remaining = factor
    # разложение на множители в диапазоне [0.5, 2.0]
    while remaining > 2.0 + 1e-6:
        steps.append(2.0); remaining /= 2.0
    while remaining < 0.5 - 1e-6:
        steps.append(0.5); remaining /= 0.5
    steps.append(remaining)
    return ",".join(f"atempo={s:.6f}" for s in steps)


def pitch_shift(src: str, dst: str, semitones: float, sr: int = 44100) -> str:
    """
    Сдвигает высоту тона на `semitones` полутонов, СОХРАНЯЯ длительность.
    Приём: asetrate (меняет и высоту, и скорость) → возвращаем скорость atempo.
    Так пословные тайминги ElevenLabs остаются валидными после сдвига.
    """
    if abs(semitones) < 0.05:
        # без сдвига — просто нормализуем в нужный формат
        run_ff(["ffmpeg", "-y", "-i", src, "-ar", str(sr), "-ac", "2", dst], label="pitch0")
        return dst
    ratio = 2.0 ** (semitones / 12.0)              # >1 = выше, <1 = ниже
    new_rate = int(round(sr * ratio))
    tempo_fix = _atempo_chain(1.0 / ratio)         # компенсируем скорость обратно
    af = f"asetrate={new_rate},aresample={sr},{tempo_fix}"
    run_ff([
        "ffmpeg", "-y", "-i", src, "-af", af,
        "-ar", str(sr), "-ac", "2", dst,
    ], label="pitch")
    return dst


def concat_demux(paths: list[str], dst: str, workdir: str,
                 reencode: bool = False, label: str = "concat",
                 fps: int | None = None) -> str:
    """
    Склейка однотипных медиа через concat-демуксер.
    reencode=False (copy) — если все входы строго одинаковы по кодеку/параметрам.
    """
    listfile = os.path.join(workdir, f"_concat_{label}.txt")
    with open(listfile, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    args = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile]
    if reencode:
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]
        if fps:
            args += ["-r", str(fps)]
    else:
        args += ["-c", "copy"]
    args += [dst]
    run_ff(args, label=label)
    return dst


# ── СЦЕПКА ПО КАДРАМ / ПЛАВНЫЕ ПЕРЕХОДЫ ────────────────────────────────────────

def extract_last_frame(src: str, dst: str) -> str:
    """Достаёт ПОСЛЕДНИЙ кадр клипа как PNG (для сцепки шотов: конец N = старт N+1)."""
    run_ff(
        ["ffmpeg", "-y", "-sseof", "-0.1", "-i", src,
         "-update", "1", "-frames:v", "1", "-q:v", "2", dst],
        label="last_frame",
    )
    return dst


def xfade_concat(paths: list[str], dst: str, transition: float,
                 has_audio: bool, fps: int, label: str = "xfade") -> str:
    """
    Склейка клипов с КРОССФЕЙДАМИ (видео xfade + опц. acrossfade аудио) вместо
    жёсткого стыка. Клипы могут быть разной длины. transition — длина перехода (сек).
    Требует реэнкод (xfade нельзя в copy-режиме). Длина итога = sum(dur) - (n-1)*T.
    """
    n = len(paths)
    if n == 1:
        # один клип — переходов нет, просто нормализуем контейнер
        args = ["ffmpeg", "-y", "-i", paths[0], "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps)]
        if has_audio:
            args += ["-c:a", "aac"]
        args += [dst]
        run_ff(args, label=label)
        return dst

    durs = [probe_duration(p) for p in paths]
    args = ["ffmpeg", "-y"]
    for p in paths:
        args += ["-i", p]

    # видео-цепочка xfade: offset = накопленная длительность - transition
    vf = []
    prev = "[0:v]"
    acc = durs[0]
    for k in range(1, n):
        off = max(0.0, acc - transition)
        out = f"[vx{k}]" if k < n - 1 else "[vout]"
        vf.append(f"{prev}[{k}:v]xfade=transition=fade:duration={transition}:offset={off:.3f}{out}")
        prev = out
        acc = acc + durs[k] - transition
    filters = ";".join(vf)
    maps = ["-map", "[vout]"]

    if has_audio:
        af = []
        aprev = "[0:a]"
        for k in range(1, n):
            out = f"[ax{k}]" if k < n - 1 else "[aout]"
            af.append(f"{aprev}[{k}:a]acrossfade=d={transition}{out}")
            aprev = out
        filters += ";" + ";".join(af)
        maps += ["-map", "[aout]"]

    args += ["-filter_complex", filters] + maps
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps)]
    if has_audio:
        args += ["-c:a", "aac"]
    args += [dst]
    run_ff(args, label=label)
    return dst


# ── ВИДЕО-ФОЛБЭК: КЛИП ИЗ КАРТИНКИ (Ken Burns) ─────────────────────────────────

def ken_burns_clip(image_path: str, dst: str, duration: float,
                   width: int, height: int, fps: int,
                   zoom: float = 1.18) -> str:
    """
    Делает живой клип из статичной картинки (медленный зум-ин + cover-crop).
    Используется как фолбэк, если image-to-video не отдал результат.
    Звука нет (голос подкладывается отдельно).
    """
    frames = max(int(round(duration * fps)), 1)
    # zoompan работает по кадрам; считаем приращение зума на кадр.
    zinc = (zoom - 1.0) / max(frames - 1, 1)
    # Апскейлим перед zoompan (он любит крупный исходник — меньше дрожания),
    # затем cover-crop в целевой кадр.
    vf = (
        f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
        f"zoompan=z='min(zoom+{zinc:.6f},{zoom})':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={width}x{height}:fps={fps},"
        f"setsar=1"
    )
    run_ff([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-t", f"{duration:.3f}", "-vf", vf, "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-profile:v", "high", "-preset", "veryfast", dst,
    ], label="kenburns")
    return dst
