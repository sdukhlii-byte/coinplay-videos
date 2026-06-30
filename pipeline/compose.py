"""
pipeline/compose.py — финальная сборка ролика на ffmpeg.

Этапы (каждый пишет промежуточный файл — удобно дебажить, как в баннерах):
  1. normalize_shot()  — клип → точная длина d_i, VIDEO_WxVIDEO_H, fps, без звука
  2. concat_video()    — склейка нормализованных клипов → body.mp4
  3. concat_voice()    — склейка пошотовых mp3, КАЖДЫЙ дополнен тишиной до d_i,
                         поэтому аудио-таймлайн совпадает с видео-таймлайном
  4. burn()            — body + voice + музыка + субтитры(ASS) + лого → body_final.mp4
  5. make_endcard()    — брендовый аутро с лого и CTA
  6. concat_final()    — body_final + endcard → output.mp4

Ключевой инвариант синхрона: длина i-й озвучки в дорожке == d_i (длина i-го шота).
Без этого голос, картинка и субтитры расходятся (дрейф накапливается по шотам).
"""

from __future__ import annotations

import os
import logging

import config as C
from pipeline.media import run_ff, probe_duration

log = logging.getLogger("compose")


# ── 1. НОРМАЛИЗАЦИЯ ШОТА ───────────────────────────────────────────────────────

def normalize_shot(src: str, dst: str, duration: float) -> None:
    """Клип → ровно `duration` сек, кадр VIDEO_WxVIDEO_H (cover-crop), FPS, без аудио."""
    vf = (
        f"scale={C.VIDEO_W}:{C.VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={C.VIDEO_W}:{C.VIDEO_H},fps={C.FPS},setsar=1,"
        f"tpad=stop_mode=clone:stop_duration=5"   # safety: дотянуть, если клип короче d_i
    )
    run_ff([
        "ffmpeg", "-y", "-i", src, "-t", f"{duration:.3f}",
        "-vf", vf, "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(C.FPS),
        "-profile:v", "high", "-preset", "veryfast", dst,
    ], label="normalize")


# ── ОБЩАЯ СКЛЕЙКА (concat demuxer) ─────────────────────────────────────────────

def _concat_demux(paths: list[str], dst: str, workdir: str, reencode: bool, label: str) -> None:
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
    run_ff(args, label=f"concat_{label}")


def concat_video(norm_paths: list[str], dst: str, workdir: str) -> None:
    # Все нормализованные клипы имеют идентичные параметры → можно copy.
    _concat_demux(norm_paths, dst, workdir, reencode=False, label="video")


# ── 3. СКЛЕЙКА ГОЛОСА С ПАДДИНГОМ ──────────────────────────────────────────────

def concat_voice(mp3_paths: list[str], durations: list[float],
                 dst_wav: str, workdir: str) -> None:
    """
    Каждую озвучку конвертируем в wav и дополняем тишиной до d_i, затем склеиваем.
    Итог: voice.wav длиной == sum(durations) == длине body.mp4, пошотово выровнено.
    """
    wavs = []
    for i, (mp, d) in enumerate(zip(mp3_paths, durations)):
        w = os.path.join(workdir, f"_voice_{i:02d}.wav")
        run_ff([
            "ffmpeg", "-y", "-i", mp,
            "-af", "apad", "-t", f"{d:.3f}",      # тишина в хвост ровно до d_i
            "-ar", "44100", "-ac", "2", w,
        ], label="voice_pad")
        wavs.append(w)
    _concat_demux(wavs, dst_wav, workdir, reencode=False, label="voice")


# ── 4. ПРОЖИГ: видео + голос + музыка + субтитры + лого ─────────────────────────

def burn(body: str, voice_wav: str, ass_path: str, logo_path: str,
         music_path: str | None, total_dur: float, dst: str) -> None:
    inputs = ["-i", body, "-i", voice_wav, "-i", logo_path]
    has_music = bool(music_path and os.path.exists(music_path))
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", music_path]

    logo_w = int(C.VIDEO_W * 0.30)
    # Экранирование пути к ASS для filtergraph (двоеточия и кавычки).
    ass_arg = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "")
    fonts_dir = C.FONTS_DIR.replace("\\", "/").replace(":", "\\:")

    fc = (
        f"[0:v]subtitles='{ass_arg}':fontsdir='{fonts_dir}'[vs];"
        f"[2:v]scale={logo_w}:-1[logo];"
        f"[vs][logo]overlay=W-w-40:40:format=auto[vout];"
        f"[1:a]aresample=44100[voc]"
    )
    if has_music:
        fc += (
            f";[3:a]volume={C.MUSIC_VOLUME},aresample=44100[mus];"
            f"[voc][mus]amix=inputs=2:duration=first:dropout_transition=0,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
        )
    else:
        fc += ";[voc]loudnorm=I=-16:TP=-1.5:LRA=11[aout]"

    # БЕЗ -shortest: длину диктует видео; -t total страхует от бесконечной музыки.
    run_ff([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", "[vout]", "-map", "[aout]",
        "-t", f"{total_dur:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-r", str(C.FPS),
        "-movflags", "+faststart", dst,
    ], label="burn")


# ── 5. ЭНД-КАРТА ───────────────────────────────────────────────────────────────

def make_endcard(logo_path: str, dst: str, cta_text: str = "COINPLAY.COM",
                 seconds: float = 2.0) -> None:
    font = C.FONT_DISPLAY
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
    run_ff([
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

def concat_final(body_final: str, endcard: str, dst: str, workdir: str) -> None:
    _concat_demux([body_final, endcard], dst, workdir, reencode=True, label="final")


# ── ОРКЕСТРАТОР КОМПОНОВКИ ─────────────────────────────────────────────────────

def compose(workdir: str, shot_clips: list[str], shot_durations: list[float],
            voice_mp3s: list[str], ass_path: str, logo_path: str,
            music_path: str | None, cta_text: str, out_path: str) -> str:
    # 1. нормализация шотов
    norm = []
    for i, (clip, d) in enumerate(zip(shot_clips, shot_durations)):
        dst = os.path.join(workdir, f"norm_{i:02d}.mp4")
        normalize_shot(clip, dst, d)
        norm.append(dst)

    # 2. видеодорожка
    body = os.path.join(workdir, "body.mp4")
    concat_video(norm, body, workdir)

    # 3. голос (паддинг до d_i → синхрон с видео)
    voice_wav = os.path.join(workdir, "voice.wav")
    concat_voice(voice_mp3s, shot_durations, voice_wav, workdir)

    total_dur = sum(shot_durations)

    # 4. прожиг
    body_final = os.path.join(workdir, "body_final.mp4")
    burn(body, voice_wav, ass_path, logo_path, music_path, total_dur, body_final)

    # 5. эндкарта
    endcard = os.path.join(workdir, "endcard.mp4")
    make_endcard(logo_path, endcard, cta_text=cta_text)

    # 6. финал
    concat_final(body_final, endcard, out_path, workdir)
    log.info("Composed final video: %s (%.2fs)", out_path, probe_duration(out_path))
    return out_path
