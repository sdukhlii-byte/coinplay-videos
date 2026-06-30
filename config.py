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

import fontutil

# Корень репозитория — все ассеты резолвим абсолютно, не полагаясь на CWD.
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
BRAND_DIR = os.path.join(BASE_DIR, "brand")
FONTS_DIR = os.path.join(BRAND_DIR, "fonts")
ASSETS_DIR = os.path.join(BRAND_DIR, "assets")

# Дисплейный шрифт субтитров/CTA. Берём ПЕРВЫЙ валидный из кандидатов и читаем его
# реальное family name из таблицы name (libass матчит именно по нему). Это лечит
# скрытый баг «битый .ttf → молчаливый фолбэк на DejaVu».
_FONT_CANDIDATES = [
    _p for _p in [
        os.environ.get("FONT_DISPLAY_PATH", ""),                 # явное переопределение
        os.path.join(FONTS_DIR, "Anton-Regular.ttf"),            # основной (жирный poster)
        os.path.join(FONTS_DIR, "BebasNeue-Regular.ttf"),        # запасной
        os.path.join(FONTS_DIR, "Oswald-Variable.ttf"),          # запасной
    ] if _p
]
FONT_DISPLAY, FONT_DISPLAY_NAME = fontutil.resolve_font(_FONT_CANDIDATES)
# Позволяем жёстко переопределить family name (если нужно подменить системным).
FONT_DISPLAY_NAME = os.environ.get("FONT_DISPLAY_NAME", FONT_DISPLAY_NAME)

LOGO_PATH = os.path.join(ASSETS_DIR, "logo_440x80_light.png")


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


def _opt(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _flag(key: str, default: bool = False) -> bool:
    return _opt(key, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


# ── ПРОВАЙДЕР ГЕНЕРАТИВНОЙ МЕДИА ───────────────────────────────────────────────
# Картинки (референсы персонажей + кейфреймы) и видео (i2v) можно гнать через
# fal ИЛИ openrouter — независимо. Свап = одна переменная окружения.
#   IMAGE_PROVIDER = fal | openrouter   (дефолт fal)
#   VIDEO_PROVIDER = fal | openrouter   (дефолт fal)
IMAGE_PROVIDER = _opt("IMAGE_PROVIDER", "fal").strip().lower()
VIDEO_PROVIDER = _opt("VIDEO_PROVIDER", "fal").strip().lower()
_USE_FAL = "fal" in (IMAGE_PROVIDER, VIDEO_PROVIDER)
_USE_OR  = "openrouter" in (IMAGE_PROVIDER, VIDEO_PROVIDER)

# ── СЕКРЕТЫ / КЛЮЧИ ────────────────────────────────────────────────────────────
AIRTABLE_TOKEN     = _require("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID   = _require("AIRTABLE_BASE_ID")
OPENAI_API_KEY     = _require("OPENAI_API_KEY")        # сценарий (вы уже его используете)
# Ключи провайдеров медиа: требуем только тот, что реально используется.
FAL_KEY            = _require("FAL_KEY") if _USE_FAL else _opt("FAL_KEY")
OPENROUTER_API_KEY = _require("OPENROUTER_API_KEY") if _USE_OR else _opt("OPENROUTER_API_KEY")
OPENROUTER_REFERER = _opt("OPENROUTER_REFERER", "")    # опц. атрибуция приложения
OPENROUTER_TITLE   = _opt("OPENROUTER_TITLE", "Coinplay")
ELEVENLABS_API_KEY = _require("ELEVENLABS_API_KEY")    # закадровый голос
TELEGRAM_TOKEN     = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT      = _require("TELEGRAM_CHAT_ID")

# Хранилище видео — S3-совместимое (Cloudflare R2 / Backblaze B2 / AWS S3).
# ОПЦИОНАЛЬНО: если переменные не заданы, заливка пропускается, ролик уходит
# только в Telegram файлом (поле Video_URL в Airtable остаётся пустым).
S3_ENDPOINT_URL    = _opt("S3_ENDPOINT_URL")    # напр. https://<acct>.r2.cloudflarestorage.com
S3_ACCESS_KEY      = _opt("S3_ACCESS_KEY")
S3_SECRET_KEY      = _opt("S3_SECRET_KEY")
S3_BUCKET          = _opt("S3_BUCKET")
S3_PUBLIC_BASE     = _opt("S3_PUBLIC_BASE")      # публичный CDN-домен бакета

STORAGE_ENABLED = all([S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_PUBLIC_BASE])

# Локальный архив готовых роликов на ПЕРСИСТЕНТНОМ томе Railway (напр. /data).
# Если задан — каждый собранный output.mp4 копируется в <DIR>/<record_id>.mp4
# ДО доставки, поэтому рендер не теряется даже если Telegram/заливка упали.
# Это бэкап «не потерять файл», НЕ публичная ссылка (URL у файла на томе нет).
LOCAL_ARCHIVE_DIR = _opt("LOCAL_ARCHIVE_DIR", "")

# ── AIRTABLE: таблица и поля ───────────────────────────────────────────────────
AIRTABLE_TABLE     = _opt("AIRTABLE_TABLE_NAME", "Videos")

# Входные поля (что задаёт человек в Airtable)
F_TOPIC     = _opt("AIRTABLE_TOPIC_FIELD",    "Name")        # тема/бриф ролика (или вертикаль)
F_STATUS    = _opt("AIRTABLE_STATUS_FIELD",   "Status")
F_LANGUAGE  = _opt("AIRTABLE_LANG_FIELD",     "Language")    # en/es/hr/lt/lv/ru/sr...
F_VERTICAL  = _opt("AIRTABLE_VERTICAL_FIELD", "Vertical")    # опц. вертикаль (casino/sportsbook/...)
F_FORMAT    = _opt("AIRTABLE_FORMAT_FIELD",   "Format")      # опц. формат скита (fruit-argument/...)
F_STYLE     = _opt("AIRTABLE_STYLE_FIELD",    "Style")       # информационное поле стиля
F_DURATION  = _opt("AIRTABLE_DURATION_FIELD", "Duration")    # целевая длина, сек (15..25)
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
    # Картинки: референс-листы персонажей + покадровые мульти-референс кейфреймы.
    # Nano Banana Pro = Gemini-image на fal, поддерживает несколько reference-картинок
    # (image_urls) для композиции нескольких персонажей в одном кадре on-model.
    "character_image": _opt("FAL_CHARACTER_MODEL", "fal-ai/nano-banana-pro"),
    "keyframe_image":  _opt("FAL_KEYFRAME_MODEL",  "fal-ai/nano-banana-pro/edit"),
    # Image-to-video. Kling v3 Pro — рабочая лошадка: дёшево, консистентность субъекта.
    # Аудио модели НЕ включаем (generate_audio=false) — звук кладём свой через ElevenLabs.
    "image_to_video":  _opt("FAL_I2V_MODEL", "fal-ai/kling-video/v3/pro/image-to-video"),
    # «Геройский» роут для финалов (опц., дороже). Veo 3.1.
    "image_to_video_hero": _opt("FAL_I2V_HERO_MODEL", "fal-ai/veo3.1/image-to-video"),
}

# ── ЭНДПОИНТЫ МОДЕЛЕЙ (OpenRouter) ─────────────────────────────────────────────
# Слаги сверять с актуальным каталогом:
#   картинки → https://openrouter.ai/api/v1/images/models
#   видео    → https://openrouter.ai/api/v1/videos/models
# Картинка одна на оба этапа (референс + кейфрейм через input_references).
OR_IMAGE_MODEL      = _opt("OR_IMAGE_MODEL", "google/gemini-2.5-flash-image")
OR_IMAGE_RESOLUTION = _opt("OR_IMAGE_RESOLUTION", "")   # "1K"/"2K"/"" (провайдер сам)
# Видео: veo-режим и kling-режим — разные слаги.
OR_VIDEO_MODEL_VEO  = _opt("OR_VIDEO_MODEL_VEO", "google/veo-3.1")
OR_VIDEO_MODEL_I2V  = _opt("OR_VIDEO_MODEL_I2V", "kwaivgi/kling-v3.0-std")

# Какие длительности клипов поддерживает i2v-модель (для квантизации длины шота).
# Kling обычно 5 / 10 сек. Подгоняем под ближайшую сверху, затем триммим в ffmpeg.
I2V_ALLOWED_DURATIONS = [int(x) for x in _opt("I2V_ALLOWED_DURATIONS", "5,10").split(",")]
I2V_RESOLUTION        = _opt("I2V_RESOLUTION", "1080p")
# Негативный промт для i2v (Kling поддерживает) — против артефактов мультяшной анимации.
I2V_NEGATIVE = _opt(
    "I2V_NEGATIVE",
    "morphing, distortion, extra limbs, extra fingers, deformed face, flickering, "
    "text, watermark, subtitles, logo, blurry, low quality"
)
# Если i2v упал (таймаут/ошибка модели) — собрать клип из кейфрейма (Ken Burns),
# чтобы ролик всё равно достроился, а не падал целиком.
I2V_FALLBACK_KENBURNS = _flag("I2V_FALLBACK_KENBURNS", True)

# ── ВТОРИЧНЫЙ ВИДЕО-ДВИЖОК (фолбэк при отказе основного по контент-политике) ────
# Когда Veo отклоняет шот ("...interests of third-party content providers" / safety),
# раньше мы сразу падали в НЕМОЙ Ken Burns — статичный слайд без звука. Теперь между
# ними есть второй i2v-движок с более мягким фильтром И нативным аудио (Seedance 1.5
# Pro), чтобы реплики персонажей НЕ терялись. Цепочка: Veo → Seedance → Ken Burns+TTS.
#   SECONDARY_VIDEO_ENABLED=1  включить вторичный движок (нужен FAL_KEY)
#   SECONDARY_VIDEO_MODEL      эндпоинт fal (сверять с каталогом, как и MODELS)
SECONDARY_VIDEO_ENABLED = _flag("SECONDARY_VIDEO_ENABLED", True)
SECONDARY_VIDEO_MODEL   = _opt("SECONDARY_VIDEO_MODEL",
                               "fal-ai/bytedance/seedance/v1.5/pro/image-to-video")
# Seedance 1.5 Pro гарантированно тянет до 720p; 1080p заявлен в API, но на 1.5 Pro
# местами капризничает — для ФОЛБЭКА берём надёжное 720p (соц-сети всё равно жмут).
SECONDARY_RESOLUTION    = _opt("SECONDARY_RESOLUTION", "720p")   # 480p/720p/1080p
# Длина клипа Seedance: 4..12 c, СТРОКОЙ. Пусто → берём из VEO_DURATION ("8s"→"8").
SECONDARY_DURATION      = _opt("SECONDARY_DURATION", "")
SECONDARY_GENERATE_AUDIO = _flag("SECONDARY_GENERATE_AUDIO", True)
# enable_safety_checker Seedance: false снижает ЛОЖНЫЕ реджекты благонадёжной
# мелодрамы (твой кейс). Это мягкий чекер, а НЕ обход контент-политики: нелегальный
# контент модель всё равно не сгенерит. Дефолт false ровно потому, что весь смысл
# вторичного движка — пройти там, где Veo ложно сработал на IP/интимности.
SECONDARY_SAFETY_CHECKER = _flag("SECONDARY_SAFETY_CHECKER", False)

# Ken Burns как ПОСЛЕДНИЙ фолбэк: озвучивать реплики шота через ElevenLabs (TTS),
# чтобы статичный кадр не уходил немым/мёртвым. Если реплик нет или TTS упал —
# тихий Ken Burns как раньше. Требует ELEVENLABS_* (они и так required в конфиге).
KENBURNS_TTS = _flag("KENBURNS_TTS", True)

# ── ФОЛБЭК КАРТИНКИ (кейфрейм заблокирован контент-фильтром) ───────────────────
# Главный гейткипер — НЕ Veo, а image-модель (Gemini/Nano Banana режет кейфрейм как
# IMAGE_PROHIBITED_CONTENT → раньше падал весь ролик). Цепочка кейфрейма теперь:
#   1) основная модель с зачищенным промптом;
#   2) она же + явная «чистая» оговорка (fully clothed / non-sexual / no gore);
#   3) пермиссивная t2i-модель (Flux на fal) — без референсов, но шот ОТРИСУЕТСЯ
#      и ролик не упадёт. Нужен FAL_KEY.
IMAGE_FALLBACK_ENABLED   = _flag("IMAGE_FALLBACK_ENABLED", True)
FAL_FALLBACK_IMAGE_MODEL = _opt("FAL_FALLBACK_IMAGE_MODEL", "fal-ai/flux/dev")

# ── ВИДЕО-ДВИЖОК ───────────────────────────────────────────────────────────────
# VIDEO_ENGINE=veo   — Veo 3.1 image-to-video с НАТИВНЫМ аудио: персонажи сами
#                      говорят свои реплики с липсинком (+эмбиент). ElevenLabs не
#                      используется. Длину шота диктует сам клип (до 8 сек).
# VIDEO_ENGINE=kling — старый маршрут: Kling i2v без звука + закадр ElevenLabs
#                      поверх + пословные субтитры. Дешевле, полный контроль текста.
VIDEO_ENGINE = _opt("VIDEO_ENGINE", "veo").strip().lower()

# Тиры Veo 3.1 (качество↔цена, цены за секунду С аудио):
#   standard — лучшее качество, $0.40/с
#   fast     — баланс,          $0.15/с   ← дефолт
#   lite     — дешёвый,         $0.05/с (720p) / $0.08/с (1080p), всегда с аудио
VEO_TIER = _opt("VEO_TIER", "fast").strip().lower()
_VEO_ENDPOINTS = {
    "standard": "fal-ai/veo3.1/image-to-video",
    "fast":     "fal-ai/veo3.1/fast/image-to-video",
    "lite":     "fal-ai/veo3.1/lite/image-to-video",
}


def veo_i2v_model() -> str:
    """Эндпоинт Veo 3.1 i2v по выбранному тиру (или явный override FAL_VEO_MODEL)."""
    override = _opt("FAL_VEO_MODEL", "")
    if override:
        return override
    return _VEO_ENDPOINTS.get(VEO_TIER, _VEO_ENDPOINTS["fast"])


VEO_DURATION   = _opt("VEO_DURATION", "8s")        # длина клипа шота: "8s"/"6s"/"4s"
VEO_RESOLUTION = _opt("VEO_RESOLUTION", "1080p")   # 720p/1080p (для std/fast цена та же)
VEO_ASPECT     = _opt("VEO_ASPECT", "9:16")        # вертикаль
VEO_GENERATE_AUDIO = _flag("VEO_GENERATE_AUDIO", True)   # пусть модель сама говорит
VEO_SAFETY     = _opt("VEO_SAFETY_TOLERANCE", "4")  # 1 (строго) .. 6 (мягко)
# Субтитры в Veo-режиме: словных таймкодов нет (нет TTS). Дефолт — БЕЗ текста вовсе:
# чистая картинка Veo «дороже» и вируснее, чем хук, налепленный поверх кадра.
#   off  — без текста на видео (дефолт);  hook — крупный хук-текст первые ~2 c.
VEO_CAPTIONS   = _opt("VEO_CAPTIONS", "off").strip().lower()
# Подкладывать ли фоновую музыку ПОД нативное аудио (по умолчанию нет — у Veo уже
# есть собственный эмбиент/речь, музыка чаще мешает).
VEO_MUSIC_UNDER = _flag("VEO_MUSIC_UNDER", False)
# В Veo-режиме шотов меньше: каждый — отдельная ~8-сек сцена с речью.
DEFAULT_SHOTS_VEO = int(_opt("DEFAULT_SHOTS_VEO", "3"))

# ── ELEVENLABS: ПУЛ ГОЛОСОВ / ПРОФИЛИ ПЕРСОНАЖЕЙ ───────────────────────────────
# Формат «фрукты спорят» живёт за счёт РАЗНЫХ голосов у персонажей. Но если у вас
# один voice_id — не беда: разводим персонажей по высоте тона (pitch) на ffmpeg,
# и они звучат по-разному из одного голоса. Это и есть режим «голос один поверх».
#
#   VOICE_MODE=multi  (дефолт) — каждый персонаж получает свой профиль (id+pitch).
#   VOICE_MODE=single          — ВСЕ реплики читает один голос (профиль 0).
#
# Профиль 0 = НАРРАТОР/дефолт. Профили 1..4 = голоса персонажей. Для профилей 1..4
# можно задать отдельные voice_id (ELEVEN_VOICE_1..4); если не заданы — берётся
# дефолтный голос языка + сдвиг тона из ELEVEN_PITCH_k (или дефолтный разброс).
ELEVEN_MODEL    = _opt("ELEVEN_MODEL", "eleven_multilingual_v2")
ELEVEN_VOICE_DEFAULT = _require("ELEVEN_VOICE_ID")     # дефолтный voice_id (профиль 0)
ELEVEN_STYLE    = float(_opt("ELEVEN_STYLE", "0.40"))  # экспрессивность реплик
VOICE_MODE      = _opt("VOICE_MODE", "multi").strip().lower()   # multi | single

ELEVEN_VOICE_BY_LANG = {
    "en": _opt("ELEVEN_VOICE_EN", ""),
    "es": _opt("ELEVEN_VOICE_ES", ""),
    "hr": _opt("ELEVEN_VOICE_HR", ""),
    "lt": _opt("ELEVEN_VOICE_LT", ""),
    "lv": _opt("ELEVEN_VOICE_LV", ""),
    "ru": _opt("ELEVEN_VOICE_RU", ""),
    "sr": _opt("ELEVEN_VOICE_SR", ""),
}

# Доп. voice_id под роли персонажей (опц.). Пусто → берём дефолтный + pitch.
_EXTRA_VOICE_IDS = {k: _opt(f"ELEVEN_VOICE_{k}", "") for k in (1, 2, 3, 4)}
# Дефолтный разброс высоты тона (полутона) для персонажей, если нет отдельных голосов.
_DEFAULT_PITCH = {1: 2.5, 2: -2.5, 3: 5.0, 4: -5.0}
_EXTRA_PITCH = {
    k: (float(_opt(f"ELEVEN_PITCH_{k}", "")) if _opt(f"ELEVEN_PITCH_{k}", "") else None)
    for k in (1, 2, 3, 4)
}

# Сколько голосовых ролей вообще доступно (нарратор + персонажи).
VOICE_ROLES = 5  # индексы 0..4


def voice_for(language: str) -> str:
    """Дефолтный (нарраторский) voice_id для языка."""
    return ELEVEN_VOICE_BY_LANG.get(language.lower(), "") or ELEVEN_VOICE_DEFAULT


def voice_profile(role: int, language: str) -> dict:
    """
    Профиль голоса для роли:
      role 0      → нарратор/дефолт (pitch 0)
      role 1..4   → персонажи (свой voice_id если задан, иначе дефолт + сдвиг тона)
    В режиме VOICE_MODE=single любая роль схлопывается в нарратора (один голос).
    Возвращает {voice_id, pitch, style}.
    """
    if VOICE_MODE == "single":
        role = 0
    role = max(0, min(int(role), VOICE_ROLES - 1))
    if role == 0:
        return {"voice_id": voice_for(language), "pitch": 0.0, "style": ELEVEN_STYLE}

    explicit_id = _EXTRA_VOICE_IDS.get(role, "")
    voice_id = explicit_id or voice_for(language)
    if _EXTRA_PITCH.get(role) is not None:
        pitch = _EXTRA_PITCH[role]
    elif explicit_id:
        pitch = 0.0                       # уже отдельный голос — сдвиг не нужен
    else:
        pitch = _DEFAULT_PITCH.get(role, 0.0)
    return {"voice_id": voice_id, "pitch": float(pitch), "style": ELEVEN_STYLE}


# ── БРЕНД-МАСКОТ (камео) ───────────────────────────────────────────────────────
# Если включено — сценаристу разрешается вывести фирменного маскота Coinplay в
# финальном шоте, чтобы он НАТИВНО подал бренд-панчлайн (а не баннер «жми бонус»).
BRAND_MASCOT_CAMEO = _flag("BRAND_MASCOT_CAMEO", True)
BRAND_NAME = _opt("BRAND_NAME", "Coinplay")
BRAND_DOMAIN = _opt("BRAND_DOMAIN", "coinplay.com")
CTA_TEXT = _opt("CTA_TEXT", "COINPLAY.COM")

# ── ВИДЕОФОРМАТ ────────────────────────────────────────────────────────────────
VIDEO_W = int(_opt("VIDEO_W", "1080"))
VIDEO_H = int(_opt("VIDEO_H", "1920"))     # вертикаль 9:16 под Reels/Shorts/TikTok
FPS     = int(_opt("FPS", "30"))

# Музыкальный бэкграунд: каталог с royalty-free треками в репо.
MUSIC_DIR = _opt("MUSIC_DIR", os.path.join(ASSETS_DIR, "music"))
MUSIC_VOLUME = float(_opt("MUSIC_VOLUME", "0.18"))   # музыка под голос, тихо

# ── ЦЕЛЬНОСТЬ / ПЕРЕХОДЫ МЕЖДУ ШОТАМИ ──────────────────────────────────────────
# XFADE_SEC > 0 — склеивать шоты кроссфейдом этой длины (сек) вместо жёсткого стыка
#                 (сглаживает «рваные» переходы). 0 = как раньше, встык.
XFADE_SEC = float(_opt("XFADE_SEC", "0"))
# FRAME_CHAIN=1 — сцепка по кадрам: первый кадр шота N+1 = последний кадр шота N.
#                 Делает последовательность бесшовной, НО рендерит шоты
#                 ПОСЛЕДОВАТЕЛЬНО (медленнее) и требует, чтобы кадр-сид был доступен
#                 видео-провайдеру: лучше всего с включённым R2 (STORAGE_*) или
#                 VIDEO_PROVIDER=openrouter (data-URL). Иначе fal может не принять сид.
FRAME_CHAIN = _flag("FRAME_CHAIN", False)

# ── ПАРАЛЛЕЛИЗМ ────────────────────────────────────────────────────────────────
# Шоты независимы (картинка/озвучка/анимация), fal-очередь масштабируется на стороне
# сервера — поэтому генерим параллельно. Это режет wall-clock в 3-5× и помогает
# уложиться в бюджет джобы Railway. 1 = строго последовательно (для дебага).
MAX_PARALLEL_JOBS = int(_opt("MAX_PARALLEL_JOBS", "4"))

# ── ТАЙМИНГ ОЗВУЧКИ / ШОТОВ ────────────────────────────────────────────────────
VOICE_GAP_SEC   = float(_opt("VOICE_GAP_SEC", "0.12"))   # пауза между репликами в шоте
VOICE_TAIL_SEC  = float(_opt("VOICE_TAIL_SEC", "0.25"))  # хвост тишины после реплик шота
SILENT_BEAT_SEC = float(_opt("SILENT_BEAT_SEC", "1.6"))  # длина «немого» шота (без реплик)
MIN_SHOT_SEC    = float(_opt("MIN_SHOT_SEC", "1.5"))

# ── БЮДЖЕТ ВРЕМЕНИ ДЖОБЫ ───────────────────────────────────────────────────────
MAX_JOB_SECONDS = int(_opt("MAX_JOB_SECONDS", "2400"))   # 40 минут
MAX_RECORDS_PER_RUN = int(_opt("MAX_RECORDS_PER_RUN", "1"))

# Дефолты ролика
DEFAULT_DURATION = int(_opt("DEFAULT_DURATION", "20"))
DEFAULT_SHOTS    = int(_opt("DEFAULT_SHOTS", "5"))
DEFAULT_LANGUAGE = _opt("DEFAULT_LANGUAGE", "en")
DEFAULT_STYLE    = _opt("DEFAULT_STYLE", "cartoon-brainrot")
DEFAULT_VERTICAL = _opt("DEFAULT_VERTICAL", "")          # пусто → берём из брифа/темы
DEFAULT_FORMAT   = _opt("DEFAULT_FORMAT", "")            # пусто → модель выберет формат
