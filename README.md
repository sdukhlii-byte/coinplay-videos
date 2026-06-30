# Coinplay Video Generator

Автогенерация коротких вертикальных «нейрослоп»-мультиков (15–20 сек) под
Reels / Shorts / TikTok. Та же модель работы, что у баннеров: **задал тему в
Airtable → крон на Railway всё сделал → готовый ролик прилетел в Telegram.**

```
Airtable(Pending)
   → GPT-4o пишет сценарий (хук → биты → CTA, разбитый на шоты)
   → Nano Banana Pro рисует персонажа-маскота (1 reference на ролик)
   → Nano Banana Pro рисует кейфрейм каждого шота (с reference → персонаж on-model)
   → Kling v3 Pro оживляет каждый кейфрейм (image-to-video, без аудио)
   → ElevenLabs озвучивает каждый шот (с пословными таймкодами)
   → ffmpeg: склейка + закадр + музыка + brainrot-субтитры + лого + энд-карта
   → S3/R2 (хостинг) + Telegram (доставка) → Airtable(Done)
```

Один ролик ≈ **$2.5–3.5** при роуте Kling (см. «Стоимость»).

---

## 1. Что уже проверено, а что требует ваших ключей

**Проверено локально (реально прогнано через ffmpeg):** весь компоновочный слой —
нормализация шотов, склейка, мукс голос+музыка, прожиг пословных ASS-субтитров,
оверлей лого, энд-карта. Смоук-тест `_smoke_compose.py` дополнительно ассертит
синхрон (озвучка короче шота → паддинг до d_i) и отсутствие обрезки финала.
Итог: корректный 1080×1920 H.264 mp4 нужной длины.

**Требует ваших ключей и одного live-смоук-теста:** модули, дёргающие внешние
API — `script_writer.py` (OpenAI), `visuals.py` (fal), `voice.py` (ElevenLabs),
`clients.py` (Airtable/S3/Telegram). Код написан под актуальные на сейчас формы
этих API, но **имена эндпоинтов и полей fal меняются часто** — перед первым
прогоном сверьте строки в `config.py → MODELS` и поля `payload` в `visuals.py`
с актуальными страницами моделей на https://fal.ai/models. Это единственное
место, где может потребоваться правка одной-двух строк.

---

## 2. Airtable: схема таблицы `Videos`

| Поле              | Тип             | Назначение                                            |
|-------------------|-----------------|-------------------------------------------------------|
| `Name`            | Single line     | Тема/промт ролика (вход)                              |
| `Status`          | Single select   | `Pending` / `In progress` / `Done` / `Error`         |
| `Language`        | Single line     | `en`/`es`/`hr`/`lt`/`lv`/`ru`/`sr`                   |
| `Style`           | Single line     | напр. `cartoon-brainrot` (пока информационное)        |
| `Duration`        | Number          | целевая длина, сек (15–20). Пусто → 18                |
| `Shots`           | Number          | число шотов. Пусто → 5                                |
| `Script_Override` | Long text       | (опц.) готовый сценарий-JSON, если не хотите авто      |
| `Video_URL`       | URL             | (выход) ссылка на готовый ролик                       |
| `Script`          | Long text       | (выход) сгенерированный сценарий — для контроля        |
| `Error_Log`       | Long text       | (выход) текст ошибки при сбое                          |

Имена полей переопределяемы через ENV (`AIRTABLE_*_FIELD`), как в баннерах.
Рабочий процесс: создаёте строку, `Status=Pending` → крон подхватывает.

---

## 3. Переменные окружения

```bash
# Airtable
AIRTABLE_TOKEN=...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE_NAME=Videos

# Модели
OPENAI_API_KEY=sk-...           # сценарий (GPT-4o)
FAL_KEY=...                     # картинки + видео (Kling/Nano Banana)
ELEVENLABS_API_KEY=...          # закадр
ELEVEN_VOICE_ID=...             # дефолтный голос
# опц. голоса по GEO: ELEVEN_VOICE_ES / _HR / _LT / _LV / _RU / _SR

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Хранилище видео (Cloudflare R2 / Backblaze B2 / AWS S3)
S3_ENDPOINT_URL=https://<acct>.r2.cloudflarestorage.com
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=coinplay-videos
S3_PUBLIC_BASE=https://cdn.coinplay.media   # публичный домен бакета

# Опционально (есть дефолты)
DEFAULT_DURATION=18
DEFAULT_SHOTS=5
MAX_RECORDS_PER_RUN=1
I2V_RESOLUTION=1080p
MUSIC_VOLUME=0.18
```

Музыку положите в `brand/assets/music/*.mp3` (1–3 royalty-free трека — бот
берёт случайный и подкладывает тихо под голос). Без музыки тоже работает.

---

## 4. Деплой на Railway

1. Залить репозиторий, Railway соберёт по `Dockerfile` (ffmpeg вшит в образ,
   Chromium НЕ нужен — легче баннерного).
2. Прописать ENV (см. выше).
3. Создать **Cron**-сервис, расписание напр. `*/30 * * * *`.
   Бюджет времени джобы — `MAX_JOB_SECONDS` (по умолчанию 40 мин), за запуск
   берётся `MAX_RECORDS_PER_RUN` записей (по умолчанию 1 — видео долгое).

---

## 5. Стоимость ролика (роут Kling, ~18 сек, 5 шотов)

| Этап                              | ≈ стоимость |
|-----------------------------------|-------------|
| Сценарий (GPT-4o)                 | $0.01       |
| Персонаж + 5 кейфреймов (Nano Banana Pro) | $0.30–0.60 |
| 5× image-to-video (Kling v3 Pro)  | ~$2.0       |
| Закадр (ElevenLabs)               | ~$0.05      |
| Музыка (библиотека)               | $0          |
| ffmpeg / Railway compute          | копейки     |
| **Итого**                         | **$2.5–3.5**|

«Геройский» роут на Veo 3.1 (`FAL_I2V_HERO_MODEL`) — в 2–3× дороже, под
избранные финалы. Свап модели = `config.py → MODELS`.

---

## 6. Локальный тест компоновки

```bash
pip install -r requirements.txt
python3 _smoke_compose.py   # синтетические клипы → проверка ffmpeg-сборки (без внешних API)
```

---

## 7. Дорожная карта (фаза 2)

- **Автопостинг** в YouTube (Data API), Instagram Reels (Graph API, нужен
  business-аккаунт), TikTok (Content Posting API). Сейчас v1 = доставка в
  Telegram, заливаете вручную.
- **Remotion** вместо ffmpeg-субтитров — программные брендовые субтитры/энд-карты
  на React/HTML/CSS (прямой аналог вашего Playwright-подхода в баннерах) для
  более «дизайнерских» подписей.
- **A/B по моделям** — параллельная генерация Kling vs Seedance vs Veo и выбор
  лучшего по эвристике/ручной оценке.
- **Кэш персонажа** — переиспользовать один reference-маскот между роликами
  (сейчас рисуется заново каждый раз — можно зафиксировать URL в ENV и сэкономить).
```
```
