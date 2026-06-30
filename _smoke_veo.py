"""
Офлайн смоук Veo-режима (нативное аудио) БЕЗ внешних API:
  • normalize_shot_av сохраняет звук; для клипа БЕЗ звука подкладывает тишину
  • compose_native склеивает A/V, прожигает хук-субтитр + лого, добавляет эндкарту
  • итог имеет аудиодорожку и корректную длину
Запуск: python3 _smoke_veo.py
"""
import os, subprocess, tempfile
for k in ["AIRTABLE_TOKEN","AIRTABLE_BASE_ID","OPENAI_API_KEY","FAL_KEY","ELEVENLABS_API_KEY",
          "TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","ELEVEN_VOICE_ID"]:
    os.environ.setdefault(k,"x")
os.environ.setdefault("VIDEO_ENGINE","veo")

import config as C
from pipeline import captions, compose, media

wd = tempfile.mkdtemp(prefix="cpvveo_")
results = {}

# 3 «клипа Veo»: два со звуком (речь имитируем синусом), один БЕЗ звука (фолбэк)
durs = [3.0, 4.0, 3.0]
clips = []
for i, d in enumerate(durs):
    src = os.path.join(wd, f"shot_{i:02d}.mp4")
    if i == 2:  # без аудио — проверяем тихий фолбэк нормализации
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"testsrc2=s=720x1280:r=30:d={d}",
                        "-t",str(d),"-c:v","libx264","-pix_fmt","yuv420p","-an",src],
                       capture_output=True)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"testsrc2=s=720x1280:r=30:d={d}",
                        "-f","lavfi","-i",f"sine=frequency={300+60*i}:duration={d}",
                        "-t",str(d),"-c:v","libx264","-pix_fmt","yuv420p",
                        "-c:a","aac","-ar","44100","-ac","2","-shortest",src],
                       capture_output=True)
    clips.append(src)

results["mixed_audio_inputs"] = (media.has_audio(clips[0]) and not media.has_audio(clips[2]))

# нормализация по отдельности: даже у немого клипа на выходе ДОЛЖЕН быть звук
norm2 = os.path.join(wd, "norm2.mp4")
compose.normalize_shot_av(clips[2], norm2)
results["silent_clip_gets_audio"] = media.has_audio(norm2)

# хук-субтитр (в Veo-режиме словных таймкодов нет — только хук)
ass = os.path.join(wd, "subs.ass")
captions.build_ass([], ass, C.VIDEO_W, C.VIDEO_H, font_name=C.FONT_DISPLAY_NAME,
                   on_screen_hook="STRAWBERRY DRAMA", hook_until=2.5)

out = os.path.join(wd, "output.mp4")
compose.compose_native(wd, clips, ass, C.LOGO_PATH, None, C.CTA_TEXT, out)

total = media.probe_duration(out)
exp = sum(durs) + 2.0  # + эндкарта
results["compose_native_duration"] = abs(total - exp) < 0.4
results["output_has_audio"] = media.has_audio(out)

subprocess.run(["ffmpeg","-y","-ss","1.0","-i",out,"-frames:v","1",
                os.path.join(wd,"frame.png")], capture_output=True)
results["frame_rendered"] = os.path.getsize(os.path.join(wd,"frame.png")) > 8000

print("---- RESULTS ----")
allok = True
for k,v in results.items():
    allok = allok and v
    print(f"{'PASS' if v else 'FAIL'}  {k}")
print(f"total={total:.2f} (exp {exp:.2f})")
print("ALL_PASS:", allok)
print("WD:", wd)
