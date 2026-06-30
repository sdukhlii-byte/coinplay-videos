"""
Смоук-тест компоновки БЕЗ внешних API.
Специально делает озвучку КОРОЧЕ длины шота (vdur < d_i), чтобы проверить:
  • паддинг голоса до d_i (синхрон),
  • отсутствие обрезки финала (раньше ломал -shortest).
"""
import os, subprocess, tempfile, json
for k in ["AIRTABLE_TOKEN","AIRTABLE_BASE_ID","OPENAI_API_KEY","FAL_KEY","ELEVENLABS_API_KEY",
          "TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","S3_ACCESS_KEY","S3_SECRET_KEY",
          "S3_BUCKET","S3_PUBLIC_BASE","ELEVEN_VOICE_ID"]:
    os.environ.setdefault(k,"x")
os.environ.setdefault("S3_ENDPOINT_URL","https://x.r2.cloudflarestorage.com")

import config as C
from pipeline import captions, compose
from pipeline.media import probe_duration

wd = tempfile.mkdtemp(prefix="cpvtest_")
durations = [3.2, 3.6, 3.0]          # длины шотов d_i
voice_len = [2.6, 3.1, 2.2]          # озвучка КОРОЧЕ d_i — провоцируем рассинхрон/обрезку
expected_body = sum(durations)       # 9.8
expected_total = expected_body + 2.0 # + эндкарта

clips=[]
for i,d in enumerate(durations):
    src=os.path.join(wd,f"shot_{i:02d}_raw.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc2=s=720x1280:r=30:d=5",
        "-f","lavfi","-i","anullsrc=r=44100:cl=stereo","-t","5",
        "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",src],capture_output=True)
    clips.append(src)

voice_mp3s=[]
for i,vl in enumerate(voice_len):
    mp=os.path.join(wd,f"voice_{i:02d}.mp3")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"sine=frequency=320:duration={vl}",
        "-ar","44100","-ac","2",mp],capture_output=True)
    voice_mp3s.append(mp)

words_global=[]; cursor=0.0
sample=[["First","big","hook"],["Now","the","duel","begins"],["You","just","won"]]
for vl,ws in zip(voice_len,sample):
    n=len(ws); step=vl/n
    for j,w in enumerate(ws):
        words_global.append({"word":w,"start":cursor+j*step,"end":cursor+(j+1)*step})
    cursor+=durations[voice_len.index(vl)]   # offset по d_i (видео-таймлайн)

ass=os.path.join(wd,"subs.ass")
captions.build_ass(words_global, ass, C.VIDEO_W, C.VIDEO_H,
                   font_name=C.FONT_DISPLAY_NAME, on_screen_hook="500% BONUS")

out=os.path.join(wd,"output.mp4")
compose.compose(wd, clips, durations, voice_mp3s, ass,
                logo_path=C.LOGO_PATH, music_path=None,
                cta_text="COINPLAY.COM", out_path=out)

# проверки
body_dur = probe_duration(os.path.join(wd,"body.mp4"))
voice_dur = probe_duration(os.path.join(wd,"voice.wav"))
total = probe_duration(out)
ok_voice_sync = abs(voice_dur - expected_body) < 0.15
ok_no_trunc   = abs(total - expected_total) < 0.25
print(f"body={body_dur:.2f} (exp {expected_body:.2f})")
print(f"voice={voice_dur:.2f} (exp {expected_body:.2f})  -> padded&synced: {ok_voice_sync}")
print(f"total={total:.2f} (exp {expected_total:.2f})  -> not truncated: {ok_no_trunc}")
# кадр для глаз
subprocess.run(["ffmpeg","-y","-ss","2.0","-i",out,"-frames:v","1",os.path.join(wd,"frame.png")],capture_output=True)
print("ASSERTS_PASS:", ok_voice_sync and ok_no_trunc)
print("WD:",wd)
