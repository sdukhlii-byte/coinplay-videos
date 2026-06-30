"""
pipeline/captions.py — генератор ASS-субтитров (libass).

Стиль «brainrot»: крупное слово по центру-низу, активное слово подсвечено и
слегка «пыхает» масштабом. Плюс крупный hook-текст в первые ~2 сек сверху.

Шрифт берём из brand/fonts (Anton — жирный дисплейный, как в баннерах).
"""

import os


def _ts(t: float) -> str:
    """Секунды → H:MM:SS.cc для ASS."""
    if t < 0:
        t = 0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(words_global: list[dict], out_path: str, video_w: int, video_h: int,
              font_name: str = "Anton", on_screen_hook: str = "",
              hook_until: float = 2.0) -> str:
    """
    words_global: [{word, start, end}] в глобальных секундах ролика.
    Возвращает путь к .ass.
    """
    fs = int(video_h * 0.058)       # ~110px при 1920
    hook_fs = int(video_h * 0.075)
    margin_v = int(video_h * 0.20)  # подъём субтитра над низом

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{font_name},{fs},&H00FFFFFF,&H00FFFFFF,&H00301040,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,{margin_v},1
Style: Hook,{font_name},{hook_fs},&H0033E0FF,&H0033E0FF,&H00301040,&H96000000,-1,0,0,0,100,100,0,0,1,8,4,8,60,60,{int(video_h*0.16)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = []

    # Hook сверху на первые секунды
    if on_screen_hook:
        lines.append(
            f"Dialogue: 0,{_ts(0.05)},{_ts(hook_until)},Hook,,0,0,0,,"
            f"{{\\fad(120,120)}}{_esc(on_screen_hook.upper())}"
        )

    # Пословные субтитры. Тянем конец слова до начала следующего, чтобы не мигало.
    n = len(words_global)
    for i, w in enumerate(words_global):
        start = float(w["start"])
        end = float(words_global[i + 1]["start"]) if i + 1 < n else float(w["end"]) + 0.15
        if end <= start:
            end = start + 0.12
        # лёгкий «поп»: масштаб 80%→100% за 90мс
        text = (
            f"{{\\fad(40,40)\\t(0,90,\\fscx100\\fscy100)\\fscx80\\fscy80}}"
            f"{_esc(w['word'].upper())}"
        )
        lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Word,,0,0,0,,{text}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    return out_path
