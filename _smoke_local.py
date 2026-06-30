"""
Офлайн смоук-тест НОВЫХ локальных кусков конвейера (без внешних API):
  • media.make_silence / pitch_shift (длительность сохраняется) / ken_burns_clip
  • voice._concat_wavs и «немой бит» synthesize_shot (пустой диалог)
  • captions.build_ass с пословной раскраской по говорящему
  • полная compose.compose на синтетических медиа c МУЛЬТИ-СПИКЕР сабами
Запуск: python3 _smoke_local.py
"""
import os, subprocess, tempfile

for k in ["AIRTABLE_TOKEN","AIRTABLE_BASE_ID","OPENAI_API_KEY","FAL_KEY","ELEVENLABS_API_KEY",
          "TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","ELEVEN_VOICE_ID"]:
    os.environ.setdefault(k,"x")

import config as C
from pipeline import captions, compose, voice as voicegen
from pipeline import media

wd = tempfile.mkdtemp(prefix="cpvlocal_")
results = {}

# ── 1) make_silence + pitch_shift сохраняет длительность ────────────────────────
sine = os.path.join(wd, "sine.wav")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=300:duration=2.0",
                "-ar","44100","-ac","2",sine], capture_output=True)
shifted = os.path.join(wd, "sine_up.wav")
media.pitch_shift(sine, shifted, semitones=5.0)
d_in, d_out = media.probe_duration(sine), media.probe_duration(shifted)
results["pitch_preserves_duration"] = abs(d_in - d_out) < 0.06

sil = os.path.join(wd, "sil.wav")
media.make_silence(sil, 0.5)
results["make_silence"] = abs(media.probe_duration(sil) - 0.5) < 0.05

# ── 2) _concat_wavs ────────────────────────────────────────────────────────────
cat = os.path.join(wd, "cat.wav")
voicegen._concat_wavs([sine, sil, shifted], cat)
results["concat_wavs"] = abs(media.probe_duration(cat) - (2.0+0.5+2.0)) < 0.1

# ── 3) synthesize_shot «немой бит» (пустой диалог, без API) ─────────────────────
wav0, dur0, words0 = voicegen.synthesize_shot(wd, 99, [], {"narrator":0}, "en")
results["silent_beat"] = (words0 == [] and abs(dur0 - C.SILENT_BEAT_SEC) < 0.05
                          and os.path.exists(wav0))

# ── 4) ken_burns_clip из картинки ──────────────────────────────────────────────
img = os.path.join(wd, "kf.png")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
                f"color=c=0x140033:s={C.VIDEO_W}x{C.VIDEO_H}",
                "-frames:v","1",img], capture_output=True)
kb = os.path.join(wd, "kb.mp4")
media.ken_burns_clip(img, kb, 3.0, C.VIDEO_W, C.VIDEO_H, C.FPS)
results["ken_burns"] = abs(media.probe_duration(kb) - 3.0) < 0.2

# ── 5) captions: пословная раскраска по говорящему ──────────────────────────────
speaker_colors = captions.palette_for(["lemon","lime","coinplay_host"])
words = [
    {"word":"I","start":0.0,"end":0.3,"speaker":"lemon"},
    {"word":"am","start":0.3,"end":0.6,"speaker":"lemon"},
    {"word":"nope","start":0.7,"end":1.1,"speaker":"lime"},
    {"word":"relax","start":1.2,"end":1.8,"speaker":"narrator"},
]
ass = os.path.join(wd, "subs.ass")
captions.build_ass(words, ass, C.VIDEO_W, C.VIDEO_H,
                   font_name=C.FONT_DISPLAY_NAME, on_screen_hook="WHO IS MORE SOUR?",
                   speaker_colors=speaker_colors)
ass_text = open(ass, encoding="utf-8").read()
# lemon→жёлтый (первый цвет палитры (255,214,10) → BBGGRR = 0AD6FF)
# narrator должен остаться БЕЗ override \1c
lemon_ok = "\\1c&H0AD6FF&" in ass_text
narrator_line = [l for l in ass_text.splitlines() if "RELAX" in l][0]
narrator_no_override = "\\1c&H" not in narrator_line
results["caption_speaker_color"] = lemon_ok and narrator_no_override

# ── 6) полная compose на синтетике с мульти-спикер сабами ───────────────────────
durations = [3.2, 2.0, 3.4]      # d_i (шот 1 — «немой», короче)
voice_len = [2.7, 0.0, 2.9]      # 0 → используем немой бит как дорожку
clips, voice_tracks = [], []
for i, d in enumerate(durations):
    src = os.path.join(wd, f"shot_{i:02d}.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"testsrc2=s=720x1280:r=30:d={d+2}",
                    "-t",str(d+2),"-c:v","libx264","-pix_fmt","yuv420p",src],
                   capture_output=True)
    clips.append(src)
    vt = os.path.join(wd, f"voice_{i:02d}.wav")
    if voice_len[i] > 0:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
                        f"sine=frequency={260+40*i}:duration={voice_len[i]}",
                        "-ar","44100","-ac","2",vt], capture_output=True)
    else:
        media.make_silence(vt, C.SILENT_BEAT_SEC)
    voice_tracks.append(vt)

# words_global со speaker, offset по d_i
wg, cursor = [], 0.0
samples = [[("lemon","SOUREST"),("lemon","ONE")],[],[("coinplay_host","CASH"),("narrator","OUT")]]
for i, ws in enumerate(samples):
    vl = max(voice_len[i], 0.6)
    for j,(sp,word) in enumerate(ws):
        step = vl/max(len(ws),1)
        wg.append({"word":word,"start":cursor+j*step,"end":cursor+(j+1)*step,"speaker":sp})
    cursor += durations[i]
ass2 = os.path.join(wd, "subs2.ass")
captions.build_ass(wg, ass2, C.VIDEO_W, C.VIDEO_H, font_name=C.FONT_DISPLAY_NAME,
                   on_screen_hook="WHO IS MORE SOUR?", speaker_colors=speaker_colors)

out = os.path.join(wd, "output.mp4")
compose.compose(wd, clips, durations, voice_tracks, ass2,
                logo_path=C.LOGO_PATH, music_path=None,
                cta_text=C.CTA_TEXT, out_path=out)

body = media.probe_duration(os.path.join(wd,"body.mp4"))
voice = media.probe_duration(os.path.join(wd,"voice.wav"))
total = media.probe_duration(out)
exp_body = sum(durations)
results["compose_voice_sync"] = abs(voice - exp_body) < 0.15
results["compose_not_truncated"] = abs(total - (exp_body+2.0)) < 0.3

# кадр на вычитку (видно ли субтитры в настоящем Anton)
subprocess.run(["ffmpeg","-y","-ss","0.5","-i",out,"-frames:v","1",
                os.path.join(wd,"frame.png")], capture_output=True)
results["frame_rendered"] = os.path.getsize(os.path.join(wd,"frame.png")) > 8000

print("---- RESULTS ----")
allok = True
for k,v in results.items():
    allok = allok and v
    print(f"{'PASS' if v else 'FAIL'}  {k}")
print(f"body={body:.2f} voice={voice:.2f} total={total:.2f} (exp body={exp_body:.2f})")
print("ALL_PASS:", allok)
print("WD:", wd)
