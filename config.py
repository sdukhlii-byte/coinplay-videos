"""
config.py — единая точка конфигурации Coinplay Video Generator.

Философия та же, что в баннерном репо: всё настраивается через ENV,
имена полей Airtable переопределяемы, эндпоинты моделей вынесены в один
словарь MODELS, чтобы свап модели = смена одной строки.

ВАЖНО про эндпоинты fal: каталог fal.ai меняется часто (Kling v3 → v3.x,
Nano Banana Pro → Pro 2 и т.д.). Перед первым запуском сверьте строки в
MODELS с актуальным каталогом: https://fal.ai/models  (фильтр video / image).
Менять нужно ТОЛЬКО здесь.
"""

import os

# Корень репозитория — все ассеты резолвим абсолютно, не полагаясь на CWD.
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
BRAND_DIR = os.path.join(BASE_DIR, "brand")
FONTS_DIR = os.path.join(BRAND_DIR, "fonts")
ASSETS_DIR = os.path.join(BRAND_DIR, "assets")

FONT_DISPLAY = os.path.join(FONTS_DIR, "Anton-Regular.ttf")   # дисплейный шрифт субтитров/CTA
FONT_DISPLAY_NAME = "Anton"                                   # internal family name для libass
LOGO_PATH = os.path.join(ASSETS_DIR, "logo_440x80_light.png")


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


def _opt(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── СЕКРЕТЫ / КЛЮЧИ ────────────────────────────────────────────────────────────
AIRTABLE_TOKEN     = _require("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID   = _require("AIRTABLE_BASE_ID")
OPENAI_API_KEY     = _require("OPENAI_API_KEY")        # сценарий (вы уже его используете)
FAL_KEY            = _require("FAL_KEY")               # видео + кадры (Kling/Nano Banana)
ELEVENLABS_API_KEY = _require("ELEVENLABS_API_KEY")    # закадровый голос
TELEGRAM_TOKEN     = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT      = _require("TELEGRAM_CHAT_ID")

# Хранилище видео — S3-совместимое (Cloudflare R2 / Backblaze B2 / AWS S3).
# imgbb из баннеров не годится: видео тяжёлые, нужен нормальный объектный сторадж.
S3_ENDPOINT_URL    = _require("S3_ENDPOINT_URL")       # напр. https://<acct>.r2.cloudflarestorage.com
S3_ACCESS_KEY      = _require("S3_ACCESS_KEY")
S3_SECRET_KEY      = _require("S3_SECRET_KEY")
S3_BUCKET          = _require("S3_BUCKET")
S3_PUBLIC_BASE     = _require("S3_PUBLIC_BASE")        # публичный CDN-домен бакета, напр. https://cdn.coinplay.media

# ── AIRTABLE: таблица и поля ───────────────────────────────────────────────────
AIRTABLE_TABLE     = _opt("AIRTABLE_TABLE_NAME", "Videos")

# Входные поля (что задаёт человек в Airtable)
F_TOPIC     = _opt("AIRTABLE_TOPIC_FIELD",    "Name")        # тема/промт ролика
F_STATUS    = _opt("AIRTABLE_STATUS_FIELD",   "Status")
F_LANGUAGE  = _opt("AIRTABLE_LANG_FIELD",     "Language")    # en/es/hr/lt/lv/ru/sr...
F_STYLE     = _opt("AIRTABLE_STYLE_FIELD",    "Style")       # cartoon-brainrot / mascot / meme ...
F_DURATION  = _opt("AIRTABLE_DURATION_FIELD", "Duration")    # целевая длина, сек (15..20)
F_SHOTS     = _opt("AIRTABLE_SHOTS_FIELD",    "Shots")       # опц. override числа шотов
F_SCRIPT_IN = _opt("AIRTABLE_SCRIPT_FIELD",   "Script_Override")  # опц. готовый сценарий (JSON)

# Выходные поля (что пишет бот)
F_VIDEO_URL = _opt("AIRTABLE_VIDEO_URL_FIELD", "Video_URL")
F_SCRIPT    = _opt("AIRTABLE_SCRIPT_OUT_FIELD", "Script")    # сгенерированный сценарий (для контроля)
F_ERROR     = _opt("AIRTABLE_ERROR_FIELD",      "Error_Log")

# Статусы
S_PENDING   = _opt("AIRTABLE_STATUS_PENDING",  "Pending")
S_PROGRESS  = _opt("AIRTABLE_STATUS_PROGRESS", "In progress")
S_DONE      = _opt("AIRTABLE_STATUS_DONE",     "Done")
S_ERROR     = _opt("AIRTABLE_STATUS_ERROR",    "Error")

AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
AT_HEADERS   = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}

# ── ЭНДПОИНТЫ МОДЕЛЕЙ (fal) ─────────────────────────────────────────────────────
# Свап модели = смена строки здесь. Параметры моделей читаются в pipeline-модулях.
MODELS = {
    # Картинки: консистентный персонаж + покадровые кейфреймы.
    # Nano Banana Pro = Gemini-image на fal, поддерживает reference-картинку для консистентности.
    "character_image": _opt("FAL_CHARACTER_MODEL", "fal-ai/nano-banana-pro"),
    "keyframe_image":  _opt("FAL_KEYFRAME_MODEL",  "fal-ai/nano-banana-pro/edit"),
    # Image-to-video. Kling v3 Pro — рабочая лошадка: дёшево, консистентность субъекта.
    # Аудио модели НЕ включаем (generate_audio=false) — звук кладём свой через ElevenLabs.
    "image_to_video":  _opt("FAL_I2V_MODEL", "fal-ai/kling-video/v3/pro/image-to-video"),
    # «Геройский» роут для финалов (опц., дороже). Veo 3.1.
    "image_to_video_hero": _opt("FAL_I2V_HERO_MODEL", "fal-ai/veo3.1/image-to-video"),
}

# Какие длительности клипов поддерживает i2v-модель (для квантизации длины шота).
# Kling обычно 5 / 10 сек. Подгоняем под ближайшую сверху, затем триммим в ffmpeg.
I2V_ALLOWED_DURATIONS = [int(x) for x in _opt("I2V_ALLOWED_DURATIONS", "5,10").split(",")]
I2V_RESOLUTION        = _opt("I2V_RESOLUTION", "1080p")

# ── ELEVENLABS ─────────────────────────────────────────────────────────────────
# voice_id на язык. Дефолт — один мультиязычный голос; переопределяйте по GEO.
ELEVEN_MODEL    = _opt("ELEVEN_MODEL", "eleven_multilingual_v2")
ELEVEN_VOICE_DEFAULT = _require("ELEVEN_VOICE_ID")     # дефолтный voice_id
ELEVEN_VOICE_BY_LANG = {
    "en": _opt("ELEVEN_VOICE_EN", ""),
    "es": _opt("ELEVEN_VOICE_ES", ""),
    "hr": _opt("ELEVEN_VOICE_HR", ""),
    "lt": _opt("ELEVEN_VOICE_LT", ""),
    "lv": _opt("ELEVEN_VOICE_LV", ""),
    "ru": _opt("ELEVEN_VOICE_RU", ""),
    "sr": _opt("ELEVEN_VOICE_SR", ""),
}


def voice_for(language: str) -> str:
    return ELEVEN_VOICE_BY_LANG.get(language.lower(), "") or ELEVEN_VOICE_DEFAULT


# ── ВИДЕОФОРМАТ ────────────────────────────────────────────────────────────────
VIDEO_W = int(_opt("VIDEO_W", "1080"))
VIDEO_H = int(_opt("VIDEO_H", "1920"))     # вертикаль 9:16 под Reels/Shorts/TikTok
FPS     = int(_opt("FPS", "30"))

# Музыкальный бэкграунд: каталог с royalty-free треками в репо.
# Положите 1-3 mp3, бот выберет случайный. Абсолютный путь — не зависим от CWD.
MUSIC_DIR = _opt("MUSIC_DIR", os.path.join(ASSETS_DIR, "music"))
MUSIC_VOLUME = float(_opt("MUSIC_VOLUME", "0.18"))   # музыка под голос, тихо

# ── БЮДЖЕТ ВРЕМЕНИ ДЖОБЫ ───────────────────────────────────────────────────────
# Видео-джоба длиннее баннерной: одна генерация может занять 3-6 минут.
# На Railway Pro лимит 60 мин. Берём 1 запись за запуск по умолчанию.
MAX_JOB_SECONDS = int(_opt("MAX_JOB_SECONDS", "2400"))   # 40 минут
MAX_RECORDS_PER_RUN = int(_opt("MAX_RECORDS_PER_RUN", "1"))

# Дефолты ролика
DEFAULT_DURATION = int(_opt("DEFAULT_DURATION", "18"))
DEFAULT_SHOTS    = int(_opt("DEFAULT_SHOTS", "5"))
DEFAULT_LANGUAGE = _opt("DEFAULT_LANGUAGE", "en")
DEFAULT_STYLE    = _opt("DEFAULT_STYLE", "cartoon-brainrot")
