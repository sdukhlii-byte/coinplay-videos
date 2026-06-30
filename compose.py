"""
pipeline/compose.py — финальная сборка ролика на ffmpeg.

Этапы (каждый пишет промежуточный файл — удобно дебажить, как в баннерах):
  1. normalize_shot()  — каждый клип → точная длина d_i, 1080x1920, fps, без звука
  2. concat_video()    — склейка нормализованных клипов → body.mp4
  3. concat_voice()    — склейка пошотовых mp3 → voice.wav (длины совпадают с клипами)
  4. burn()            — body + voice + музыка + субтитры(ASS) + лого → body_final.mp4
  5. make_endcard()    — 2-сек брендовый аутро с лого и CTA
  6. concat_final()    — body_final + endcard → output.mp4

Возвращает путь к итоговому mp4.
"""

import os
import json
import shutil
import logging
import subprocess

import config as C

log = logging.getLogger("compose")


def _run(args: list[str], label: str = ""):
    log.info(f"ffmpeg[{label}]: {' '.join(args[:6])} ...")
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg[{label}] failed:\n{p.stderr[-1500:]}")


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


# ── 1. НОРМАЛИЗАЦИЯ ШОТА ───────────────────────────────────────────────────────

def normalize_shot(src: str, dst: str, duration: float):
    """Клип → ровно `duration` сек, кадр VIDEO_WxVIDEO_H (cover-crop), FPS, без аудио."""
    vf = (
        f"scale={C.VIDEO_W}:{C.VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={C.VIDEO_W}:{C.VIDEO_H},fps={C.FPS},setsar=1,"
        f"tpad=stop_mode=clone:stop_duration=5"   # safety: дотянуть, если клип короче
    )
    _run([
        "ffmpeg", "-y", "-i", src, "-t", f"{duration:.3f}",
        "-vf", vf, "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(C.FPS),
        "-profile:v", "high", "-preset", "veryfast", dst,
    ], label="normalize")


# ── 2. СКЛЕЙКА ВИДЕО ───────────────────────────────────────────────────────────

def _concat_demux(paths: list[str], dst: str, workdir: str, reencode: bool, label: str):
    listfile = os.path.join(workdir, f"_concat_{label}.txt")
    with open(listfile, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    args = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile]
    if reencode:
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-r", str(C.FPS)]
    else:
        args += ["-c", "copy"]
    args += [dst]
    _run(args, label=f"concat_{label}")


def concat_video(norm_paths: list[str], dst: str, workdir: str):
    _concat_demux(norm_paths, dst, workdir, reencode=False, label="video")


# ── 3. СКЛЕЙКА ГОЛОСА ──────────────────────────────────────────────────────────

def concat_voice(mp3_paths: list[str], dst_wav: str, workdir: str):
    """mp3 шотов → единый wav (44.1k stereo). Через промежуточные wav для надёжности."""
    wavs = []
    for i, mp in enumerate(mp3_paths):
        w = os.path.join(workdir, f"_voice_{i:02d}.wav")
        _run(["ffmpeg", "-y", "-i", mp, "-ar", "44100", "-ac", "2", w], label="voice2wav")
        wavs.append(w)
    _concat_demux(wavs, dst_wav, workdir, reencode=False, label="voice")


# ── 4. ПРОЖИГ: видео + голос + музыка + субтитры + лого ─────────────────────────

def burn(body: str, voice_wav: str, ass_path: str, logo_path: str,
         music_path: str | None, dst: str):
    fonts_dir = os.path.join("brand", "fonts")
    inputs = ["-i", body, "-i", voice_wav, "-i", logo_path]
    has_music = bool(music_path and os.path.exists(music_path))
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", music_path]

    logo_w = int(C.VIDEO_W * 0.30)
    # экранируем путь к ass для фильтра
    ass_arg = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "")

    fc = (
        f"[0:v]subtitles='{ass_arg}':fontsdir='{fonts_dir}'[vs];"
        f"[2:v]scale={logo_w}:-1[logo];"
        f"[vs][logo]overlay=W-w-40:40:format=auto[vout];"
        f"[1:a]aresample=44100,apad=pad_dur=0.2[voc]"
    )
    if has_music:
        fc += (
            f";[3:a]volume={C.MUSIC_VOLUME},aresample=44100[mus];"
            f"[voc][mus]amix=inputs=2:duration=first:dropout_transition=0,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
        )
        amap = "[aout]"
    else:
        fc += f";[voc]loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
        amap = "[aout]"

    _run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", "[vout]", "-map", amap,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-r", str(C.FPS),
        "-movflags", "+faststart", dst,
    ], label="burn")


# ── 5. ЭНД-КАРТА ───────────────────────────────────────────────────────────────

def make_endcard(logo_path: str, dst: str, cta_text: str = "COINPLAY.COM",
                 seconds: float = 2.0):
    fonts_dir = os.path.join("brand", "fonts")
    font = os.path.join(fonts_dir, "Anton-Regular.ttf")
    logo_w = int(C.VIDEO_W * 0.55)
    bg = f"color=c=0x140033:s={C.VIDEO_W}x{C.VIDEO_H}:r={C.FPS}:d={seconds}"
    fc = (
        f"[0:v]format=yuv420p[bg];"
        f"[1:v]scale={logo_w}:-1[logo];"
        f"[bg][logo]overlay=(W-w)/2:(H-h)/2-120[bv];"
        f"[bv]drawtext=fontfile='{font}':text='{cta_text}':"
        f"fontcolor=0x33E0FF:fontsize={int(C.VIDEO_H*0.045)}:"
        f"x=(w-text_w)/2:y=H/2+120:borderw=3:bordercolor=0x301040[vout]"
    )
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", bg,
        "-i", logo_path,
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={seconds}",
        "-filter_complex", fc,
        "-map", "[vout]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", "-r", str(C.FPS), "-t", f"{seconds}",
        "-movflags", "+faststart", dst,
    ], label="endcard")


# ── 6. ФИНАЛЬНАЯ СКЛЕЙКА ───────────────────────────────────────────────────────

def concat_final(body_final: str, endcard: str, dst: str, workdir: str):
    _concat_demux([body_final, endcard], dst, workdir, reencode=True, label="final")


# ── ОРКЕСТРАТОР КОМПОНОВКИ ─────────────────────────────────────────────────────

def compose(workdir: str, shot_clips: list[str], shot_durations: list[float],
            voice_mp3s: list[str], ass_path: str, logo_path: str,
            music_path: str | None, cta_text: str, out_path: str) -> str:
    # 1. нормализация
    norm = []
    for i, (clip, d) in enumerate(zip(shot_clips, shot_durations)):
        dst = os.path.join(workdir, f"norm_{i:02d}.mp4")
        normalize_shot(clip, dst, d)
        norm.append(dst)
    # 2. видео
    body = os.path.join(workdir, "body.mp4")
    concat_video(norm, body, workdir)
    # 3. голос
    voice_wav = os.path.join(workdir, "voice.wav")
    concat_voice(voice_mp3s, voice_wav, workdir)
    # 4. прожиг
    body_final = os.path.join(workdir, "body_final.mp4")
    burn(body, voice_wav, ass_path, logo_path, music_path, body_final)
    # 5. эндкарта
    endcard = os.path.join(workdir, "endcard.mp4")
    make_endcard(logo_path, endcard, cta_text=cta_text)
    # 6. финал
    concat_final(body_final, endcard, out_path, workdir)
    dur = _probe_duration(out_path)
    log.info(f"Composed final video: {out_path} ({dur:.2f}s)")
    return out_path
