"""
pipeline/captions.py — генератор ASS-субтитров (libass).

Стиль «brainrot»: крупное слово по центру-низу, активное слово слегка «пыхает»
масштабом; плюс крупный hook-текст сверху первые ~2 сек.

НОВОЕ: пословная РАСКРАСКА ПО ГОВОРЯЩЕМУ. В сюжетных скитах персонажи спорят/
перебивают друг друга — поэтому слово подсвечивается цветом текущего спикера
(narrator → белый). Это резко повышает читаемость диалогов. Раскраска включается,
если в словах есть ключ "speaker" и передан `speaker_colors`. Без них поведение
полностью прежнее (обратная совместимость со смоук-тестом и legacy-роликами).

ВАЖНО про цвета ASS: формат &HAABBGGRR (байты в порядке alpha-blue-green-red),
а НЕ RGB. Хелпер _ass() переводит человеческий (r,g,b) в правильный порядок —
из-за обратного порядка фирменный циан иначе рендерился бы жёлтым.
"""

from __future__ import annotations


# ── ЦВЕТА ──────────────────────────────────────────────────────────────────────

def _ass(r: int, g: int, b: int, a: int = 0) -> str:
    """(r,g,b[,alpha]) → строка цвета ASS &HAABBGGRR. alpha: 0=непрозрачно."""
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


def _c1(rgb: tuple[int, int, int]) -> str:
    """Инлайн-override основного цвета слова: \\1c&HBBGGRR&."""
    r, g, b = rgb
    return f"\\1c&H{b:02X}{g:02X}{r:02X}&"


WHITE        = _ass(255, 255, 255)
BRAND_CYAN   = _ass(51, 224, 255)     # #33E0FF
OUTLINE_DARK = _ass(48, 16, 64)       # #301040 тёмно-фиолетовый
SHADOW_SEMI  = _ass(0, 0, 0, 0x64)    # полупрозрачная тень

WHITE_RGB = (255, 255, 255)

# Палитра по умолчанию для спикеров (яркие, контрастные на тёмной обводке).
# Используется, если вызывающая сторона не передала свой speaker_colors.
DEFAULT_SPEAKER_PALETTE = [
    (255, 214, 10),    # жёлтый
    (51, 224, 255),    # бренд-циан
    (255, 99, 132),    # розово-красный
    (124, 252, 130),   # салатовый
    (190, 150, 255),   # фиолетовый
]


# ── ВРЕМЯ / ЭКРАНИРОВАНИЕ ──────────────────────────────────────────────────────

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
    """Экранируем символы, ломающие синтаксис ASS override-блоков."""
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def palette_for(speaker_ids: list[str]) -> dict[str, tuple[int, int, int]]:
    """
    Утилита: построить speaker_colors для списка id персонажей
    (narrator не включаем — он всегда белый). Цвета берём из палитры по кругу.
    """
    colors: dict[str, tuple[int, int, int]] = {}
    i = 0
    for sid in speaker_ids:
        if sid == "narrator":
            continue
        colors[sid] = DEFAULT_SPEAKER_PALETTE[i % len(DEFAULT_SPEAKER_PALETTE)]
        i += 1
    return colors


# ── СБОРКА ─────────────────────────────────────────────────────────────────────

def build_ass(words_global: list[dict], out_path: str, video_w: int, video_h: int,
              font_name: str = "Anton", on_screen_hook: str = "",
              hook_until: float = 2.0,
              speaker_colors: dict[str, tuple[int, int, int]] | None = None) -> str:
    """
    words_global: [{word, start, end, speaker?}] в глобальных секундах ролика
    (тайминги без значений пропускаются вызывающей стороной).

    speaker_colors: {speaker_id: (r,g,b)} — цвет активного слова по говорящему.
    Если None или у слова нет "speaker" → слово белое (как раньше).

    Возвращает путь к .ass.
    """
    fs       = int(video_h * 0.058)    # ~110px при 1920
    hook_fs  = int(video_h * 0.075)
    margin_v = int(video_h * 0.20)     # подъём субтитра над низом

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{font_name},{fs},{WHITE},{WHITE},{OUTLINE_DARK},{SHADOW_SEMI},-1,0,0,0,100,100,0,0,1,7,3,2,60,60,{margin_v},1
Style: Hook,{font_name},{hook_fs},{BRAND_CYAN},{BRAND_CYAN},{OUTLINE_DARK},{SHADOW_SEMI},-1,0,0,0,100,100,0,0,1,8,4,8,60,60,{int(video_h*0.16)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines: list[str] = []

    # Hook сверху первые секунды
    if on_screen_hook:
        lines.append(
            f"Dialogue: 0,{_ts(0.05)},{_ts(hook_until)},Hook,,0,0,0,,"
            f"{{\\fad(120,120)}}{_esc(on_screen_hook.upper())}"
        )

    # Пословные субтитры. Конец слова тянем до начала следующего, чтобы не мигало.
    n = len(words_global)
    for i, w in enumerate(words_global):
        start = float(w["start"])
        end = float(words_global[i + 1]["start"]) if i + 1 < n else float(w["end"]) + 0.15
        if end <= start:
            end = start + 0.12

        # Цвет активного слова по говорящему (narrator/неизвестный → белый).
        rgb = WHITE_RGB
        if speaker_colors:
            sp = w.get("speaker")
            if sp and sp != "narrator" and sp in speaker_colors:
                rgb = speaker_colors[sp]
        color_tag = "" if rgb == WHITE_RGB else _c1(rgb)

        # лёгкий «поп»: масштаб 80%→100% за 90 мс
        text = (
            f"{{\\fad(40,40)\\t(0,90,\\fscx100\\fscy100)\\fscx80\\fscy80{color_tag}}}"
            f"{_esc(w['word'].upper())}"
        )
        lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Word,,0,0,0,,{text}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    return out_path
