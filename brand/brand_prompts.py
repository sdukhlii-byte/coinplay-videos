"""
brand/brand_prompts.py — бренд-библиотека и творческое ядро видеогенератора.

В отличие от MVP (один фикс. маскот, повторяемый во всех шотах), здесь —
МУЛЬТИПЕРСОНАЖНАЯ сюжетная модель «TikTok brainrot»:

  • BRAND_WORLD     — единый визуальный «скин» Coinplay для ЛЮБОГО каста
  • MASCOT_BIBLE    — опциональный фирменный маскот для камео в финале
  • FORMATS         — библиотека форматов скитов (фрукты спорят, суд, и т.д.)
  • SCENE_MOODS     — настроения сцены
  • SCRIPT_SYSTEM   — system-промт сценариста: каст + сюжет + НАТИВНЫЙ бренд
  • build_*         — сборщики промтов для референс-листов / кейфреймов / анимации

Идея жанра: яркие странные персонажи СО ХАРАКТЕРОМ спорят/соревнуются (резкий хук
в первые 2 сек → эскалация → твист → нативный бренд-панчлайн Coinplay). Визуальный
стиль кадра задаётся ЗДЕСЬ, на этапе картинки — именно картинка определяет
«мультяшность», i2v потом просто оживляет.
"""

from __future__ import annotations

import os
import re

# ── ЕДИНЫЙ ВИЗУАЛЬНЫЙ «СКИН» БРЕНДА ─────────────────────────────────────────────
# Применяется ко ВСЕМ роликам поверх любого каста, чтобы мир выглядел «как Coinplay».
# RENDER_STYLE переключает рендер, НЕ трогая брендовые приметы (фиолет/сферы/монеты):
#   cinematic (дефолт) — полуреалистичный кино-3D, человекоподобные тела, кожа с
#                        сабсёрфейсом, крупные эмоции (как в Pixar-фичере);
#   cartoon            — прежний яркий мультяшный стиль.
_RENDER_STYLE = os.environ.get("RENDER_STYLE", "cinematic").strip().lower()

# Брендовое ОКРУЖЕНИЕ (приметы Coinplay) — общее для обоих стилей, не меняем.
# ВАЖНО: НЕ упоминаем здесь само слово-бренд — image-модель честно рисует его как
# надпись в небе/на вывесках. Бренд держим в РЕЧИ, энд-карте, лого-оверлее и
# эмблеме маскота — НЕ в промпте картинки. Идентичность держат фиолет/сферы/монеты.
_BRAND_ENV = (
    "a premium neon crypto-casino world: deep indigo-to-violet gradient environment, glossy "
    "volumetric purple spheres floating as signature brand elements, neon magenta and "
    "electric-blue rim lighting, golden coin particles and subtle crypto glyphs drifting "
    "in the air"
)

if _RENDER_STYLE == "cartoon":
    BRAND_WORLD = (
        f"vibrant stylized 3D cartoon set in {_BRAND_ENV}, high color saturation, punchy "
        "contrast, playful energetic mood, cinematic yet cartoonish, smooth global "
        "illumination, soft depth of field, Pixar-meets-streetwear render quality"
    )
else:  # cinematic / realistic (дефолт)
    BRAND_WORLD = (
        f"cinematic semi-realistic 3D animation, Disney-Pixar feature-film quality, set in "
        f"{_BRAND_ENV}; anthropomorphic characters with believable human-like bodies and "
        "natural proportions, soft subsurface-scattering skin with fine micro-surface "
        "detail, highly expressive faces capable of subtle nuanced emotion, rich volumetric "
        "cinematic key lighting, shallow depth of field, high dynamic range, polished "
        "film-grade render"
    )

_BRAND_WORLD_LEGACY = (
    "vibrant stylized 3D cartoon in the Coinplay brand world: deep indigo-to-violet "
    "gradient environment, glossy volumetric purple spheres floating as signature brand "
    "elements, neon magenta and electric-blue rim lighting, golden coin particles and "
    "subtle crypto glyphs drifting in the air, high color saturation, punchy contrast, "
    "playful energetic mood, cinematic yet cartoonish, smooth global illumination, "
    "soft depth of field, Pixar-meets-streetwear render quality"
)

# Композиционные требования под вертикаль 9:16. Жёсткий запрет любого текста —
# никаких надписей, вывесок, логотипов, цифр (их рисует image-модель и это палево).
FRAMING_9x16 = (
    "vertical 9:16 composition; choose shot scale for emotional impact — wide, medium, "
    "or a BOLD emotional close-up on the face when the moment calls for it; keep the main "
    "subject clearly framed. ABSOLUTELY NO text of any kind in the image: no words, no "
    "letters, no numbers, no captions, no signage, no shop/neon text, no logos, no "
    "watermarks, no UI — clean textless frame"
)

# ── ФИРМЕННЫЙ МАСКОТ (опциональное камео в финале) ─────────────────────────────
# Появляется только если включён BRAND_MASCOT_CAMEO — чтобы нативно подать бренд.
MASCOT_BIBLE = (
    "a sly, confident anthropomorphic fox-like crypto host with "
    "glowing violet eyes, wearing a sleek dark hoodie with a subtle glowing violet 'C' "
    "crest emblem, a thin gold chain and oversized headphones around the neck; stylized 3D "
    "cartoon, exaggerated expressive face, big readable eyes, clean bold shapes"
)
MASCOT_ID = "coinplay_host"

# ── НАСТРОЕНИЯ СЦЕНЫ ───────────────────────────────────────────────────────────
SCENE_MOODS = {
    "win":     "explosive jackpot celebration, golden coins erupting everywhere, confetti cannons, screen shaking with triumphant energy",
    "hype":    "frenetic hype energy, a character lunging at the viewer, speed lines, things flying around the frame",
    "lucky":   "slot / roulette spinning at insane speed, slamming to a stop, sparks and sparkles bursting, lucky-charm chaos",
    "crypto":  "glowing crypto charts rocketing upward, bitcoin and ethereum coins whirling around the scene, numbers exploding",
    "vs":      "two characters slamming into a face-off, duel energy, dramatic stadium lights snapping on, electric tension",
    "argue":   "characters loudly screaming in each other's faces, leaning in, exaggerated bug-eyed angry-funny expressions, veins and sweat drops popping",
    "smug":    "one character ice-cold and smug while another completely loses it and flails, sharp contrast of confidence vs panic",
    "shock":   "characters in comedic full-body shock, jaws hitting the floor, eyes bulging out cartoon-style, motion lines and freeze-frame",
    "reveal":  "a character whipping around to reveal a giant glowing screen, dramatic light blast, everyone's heads snapping toward it",
    "chaos":   "total slapstick mayhem, things crashing and flying, a gremlin-energy troublemaker wreaking havoc, everyone reacting big",
}

# ── БИБЛИОТЕКА ФОРМАТОВ СКИТОВ ──────────────────────────────────────────────────
# Сценарист либо получает формат на вход, либо выбирает сам. Каждый формат — короткая
# «затравка» сцены/каста, которая хорошо залетает в коротком вертикальном видео.
FORMATS = {
    "fruit-argument":
        "anthropomorphic fruits (or snacks) with faces and tiny limbs loudly arguing with "
        "each other on a kitchen counter or fridge shelf; each fruit has a strong opinion "
        "and a distinct personality.",
    "courtroom":
        "an absurd courtroom: a stern judge, a nervous defendant and an over-the-top "
        "prosecutor, all anthropomorphic objects or animals, arguing a ridiculous case.",
    "sports-commentary":
        "two mascot commentators in a booth hyping up a match between two rival characters, "
        "fast back-and-forth play-by-play energy.",
    "vs-duel":
        "two rival characters facing off like a fighting-game select screen, trash-talking "
        "before a showdown.",
    "street-interview":
        "a character with a microphone interviewing absurd characters on the street; each "
        "gives a punchy, unexpected answer.",
    "monster-roommates":
        "weird little monsters or creatures sharing a flat and bickering about everyday "
        "things in a funny way.",
    "podcast":
        "two characters sitting at a podcast table with mics, confidently debating a hot take.",
    "infomercial":
        "an over-the-top late-night infomercial host pitching to a skeptical sidekick, "
        "energy escalating to absurd levels.",
    "animals-meeting":
        "animals in a tiny corporate meeting room arguing over a plan on a whiteboard.",
    "menace-pet":
        "a small unhinged gremlin-energy animal (e.g. a chaotic ginger cat or feral little "
        "creature) with huge expressive eyes who keeps causing escalating slapstick havoc — "
        "knocking things over, body-slamming objects, sprinting through the scene — while a "
        "deadpan owner or rival reacts; cartoonish, bloodless, Tom-&-Jerry / Looney-Tunes "
        "level mayhem played purely for laughs, building to a sudden satisfying payoff.",
    "chaos-spiral":
        "one tiny problem instantly snowballs into absurd over-the-top disaster as a "
        "hyperactive troublemaker character makes every beat worse — fast, escalating, "
        "physical comedy with big reactions and a hard comedic button at the end.",
}

DEFAULT_FORMAT_HINT = (
    "pick the single funniest absurd format for this vertical (a great default is two or "
    "three characters loudly arguing, e.g. fruits on a counter)."
)


# ── ПРОМТЫ КАРТИНОК ─────────────────────────────────────────────────────────────

# Санитайзер: Gemini/Nano-Banana режут антропоморфную «романтику»/интимность как
# IMAGE_PROHIBITED_CONTENT даже в безобидной рекламной мелодраме. Нейтрализуем
# рискованные формулировки в visual/motion/design — делаем сцену ЯВНО несексуальной
# (это снижает ЛОЖНЫЕ блоки, а не добавляет «взрослый» контент).
_RISKY_SUBS = [
    (r"\bpull(?:s|ed|ing)?\s+(?:her|him|them)\s+(?:in\s+)?close\b", "stands close to"),
    (r"\b(?:faces?|lips?)\s+(?:are\s+)?(?:just\s+)?inches?\s+apart\b", "faces near each other"),
    (r"\binches?\s+apart\b", "near each other"),
    (r"\bbreath\s+(?:catch|hitch)\w*\b", "a surprised expression"),
    (r"\b(?:passionate(?:ly)?\s+)?kiss\w*\b", "dramatic moment"),
    (r"\bembrac\w+\b", "stands with"),
    (r"\bcaress\w*\b", "gestures toward"),
    (r"\b(?:sensual|seductive|sultry|steamy|erotic)\b", "dramatic"),
    (r"\bintimate(?:ly)?\b", "tense dramatic"),
    (r"\blingerie\b", "outfit"),
    (r"\bcleavage\b", ""),
    (r"\bbare\s+(?:chest|skin|shoulders?|back)\b", "outfit"),
    (r"\b(?:nude|naked|topless)\b", "fully clothed"),
    # каскад жести для chaos-формата (Veo/Gemini блокируют реалистичную кровь):
    (r"\bblood(?:y|ied)?\b", ""),
    (r"\bgore\b", ""),
    (r"\bgory\b", "cartoonish"),
    (r"\bgraphic\s+violence\b", "slapstick"),
]


def sanitize_scene_text(text: str) -> str:
    """Нейтрализует формулировки, на которые срабатывает image-safety-фильтр."""
    if not text:
        return text
    out = text
    for pat, repl in _RISKY_SUBS:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


# Позитивная «чистая» оговорка — добавляется при РЕТРАЕ заблокированного кейфрейма
# (а также в финальном flux-фолбэке), чтобы явно увести модель от запрещёнки.
IMAGE_SAFETY_CLAUSE = (
    " All characters are fully clothed and non-sexual; wholesome, brand-safe advertising "
    "image; no nudity, no sexual or suggestive content, no gore."
)

# Оговорка ОРИГИНАЛЬНОСТИ — против реджектов «interests of third-party content providers»
# (Veo/Gemini принимают наших антропоморфов за чужой IP: лиса за Зверополис и т.п.).
# Персонажи и правда оригинальные, поэтому это не обход, а корректное уточнение.
ORIGINALITY_CLAUSE = (
    "All characters and elements are completely original designs, not based on or resembling "
    "any existing movie, game, cartoon, franchise, studio or brand character; no copyrighted "
    "or trademarked characters, logos or intellectual property."
)


def build_character_ref_prompt(member: dict, setting: str = "") -> str:
    """
    Промт для ОДНОГО референс-листа персонажа (генерится 1 раз на персонажа).
    member: {id, name, design, ...}. Чистый фон-студия — чтобы потом чисто
    переносить персонажа в кейфреймы через мульти-референс.
    """
    name = member.get("name") or member.get("id", "character")
    design = sanitize_scene_text(member.get("design", "").strip())
    return (
        f"Full-body character reference sheet of a single character named '{name}'. "
        f"Character design: {design}. "
        f"{BRAND_WORLD}. "
        "Render as a premium anthropomorphic character with a believable, human-like body, "
        "natural proportions and posture, and a highly expressive face built for subtle, "
        "nuanced emotion (lead-character quality, like a Pixar hero). "
        f"Clean dark violet studio background, neutral confident pose, front view, full "
        f"body clearly visible, sharp focus, high detail, no other characters. "
        f"This is a reference sheet used to keep this exact character identical in later scenes."
    )


def build_mascot_ref_prompt() -> str:
    """Референс-лист фирменного маскота (для камео)."""
    return (
        f"Full-body character reference sheet of {MASCOT_BIBLE}. "
        f"{BRAND_WORLD}. "
        f"Clean dark violet studio background, neutral confident standing pose, front view, "
        f"full body visible, sharp focus, high detail, no other characters. "
        f"Reference sheet to keep the mascot identical across scenes."
    )


def build_keyframe_prompt(shot: dict, cast_by_id: dict, setting: str = "") -> str:
    """
    Промт кейфрейма шота. Передаётся ВМЕСТЕ с референс-картинками персонажей,
    присутствующих в шоте (image_urls). Явно называем каждого персонажа и его дизайн,
    чтобы edit-модель знала, кто есть кто, и держала их on-model.
    """
    present_ids = shot.get("characters") or list(cast_by_id.keys())
    present = [cast_by_id[c] for c in present_ids if c in cast_by_id]

    if present:
        roster = "; ".join(
            f"{m.get('name') or m.get('id')} ({sanitize_scene_text(m.get('design','').strip())})"
            for m in present
        )
        keep = (
            "Use the provided reference images. Keep EACH of these characters exactly "
            "identical to their reference (same face, colors, shapes, proportions): "
            f"{roster}."
        )
        if len(present) > 1:
            keep += " Place them together in the same scene, interacting naturally."
        is_broll = False
    else:
        keep = "Cinematic establishing shot of the location below — no characters in frame."
        is_broll = True

    # Главный сдвиг под вирусный эталон: НЕ позированный портрет, а кадр-стоп
    # ПИКОВОГО ДЕЙСТВИЯ с динамичной камерой (как стоп-кадр из трейлера), иначе i2v
    # нечего продолжать и персонаж «стоит столбом».
    if is_broll:
        action_line = (
            "Single photoreal cinematic establishing film still: a moving-camera shot of the "
            "location with depth, atmosphere and momentum (low racing dolly, sweeping crane, or "
            "push-in), like a B-roll cut from a high-end trailer."
        )
    else:
        action_line = (
            "Single photoreal cinematic FILM STILL caught at a DYNAMIC PEAK-ACTION moment — the "
            "subject MID-MOTION (mid-stride, mid-leap, mid-gesture, mid-reaction), NOT a static "
            "pose; bold dynamic camera angle (low hero angle, over-the-shoulder, dutch tilt, or "
            "moving-camera motion blur); strong sense of momentum, as if grabbed from a high-end "
            "animated-feature trailer."
        )

    parts = [
        keep,
        f"Scene: {sanitize_scene_text(shot.get('visual','').strip())}.",
        (f"Setting: {setting.strip()}." if setting else ""),
        SCENE_MOODS.get(str(shot.get("mood", "")).lower().strip(), ""),
        action_line,
        # Бренд — СДЕРЖАННЫЙ акцент в РЕАЛЬНОЙ киношной локации, а не «фиолетовый суп»
        # на весь кадр: иначе всё выглядит как баннер-реклама, а не как кино из рилса.
        "Grounded, real cinematic location with believable detail; only SUBTLE brand accents "
        "(a few violet spheres or golden-coin glints far in the background), never a flat purple "
        "void. Photoreal animated-feature render: cinematic color grade, volumetric light, "
        "shallow depth of field, film grain, high dynamic range.",
        ORIGINALITY_CLAUSE,
        FRAMING_9x16 + ".",
    ]
    return " ".join(p for p in parts if p)


def build_motion_prompt(shot: dict) -> str:
    """Промт движения для image-to-video (что оживляем в кадре)."""
    motion = sanitize_scene_text(shot.get("motion", "").strip())
    n = len(shot.get("characters") or [])
    ensemble = (
        "the characters explode into expressive physical comedy, big gestures and exaggerated "
        "reactions at each other, "
        if n >= 2 else
        "the character bursts into expressive over-the-top physical action, "
    )
    base = (
        f"High-energy viral cartoon animation: {ensemble}"
        "exaggerated squash-and-stretch cartoon physics, snappy comedic timing, dynamic camera "
        "with quick push-ins and a touch of screen-shake on impacts, floating brand spheres drift, "
        "golden coin particles shimmer. Cartoonish bloodless slapstick only — never graphic. "
        "Keep every character on-model and stable: no morphing, no extra limbs, no face distortion. "
        "No on-screen text, letters, captions, logos or watermarks."
    )
    return f"{motion}. {base}" if motion else base


_VEO_LANG_NAMES = {
    "en": "English", "es": "Spanish", "hr": "Croatian", "lt": "Lithuanian",
    "lv": "Latvian", "ru": "Russian", "sr": "Serbian", "pl": "Polish",
}


def build_veo_prompt(shot: dict, cast_by_id: dict, setting: str = "",
                     language: str = "en") -> str:
    """
    Промт для Veo 3.1 image-to-video с НАТИВНЫМ аудио. Помимо движения встраиваем
    блок реплик в формате, который Veo проговаривает с липсинком:

        ...scene/motion...
        Dialogue:
        Lemon (angry cartoon lemon): "I am the sourest one here!"
        Lime (smug cartoon lime): "In your dreams, yellow boy."

    Реплики — на языке ролика; модель сама озвучит нужный голос на персонажа.
    """
    motion = sanitize_scene_text(shot.get("motion", "").strip())
    visual = sanitize_scene_text(shot.get("visual", "").strip())
    mood = SCENE_MOODS.get(str(shot.get("mood", "")).lower().strip(), "")
    lang_name = _VEO_LANG_NAMES.get(language.lower(), language)

    scene = (
        f"Animate this image into a high-energy viral vertical TikTok cartoon. {visual}. {mood} "
        f"{motion + '. ' if motion else ''}"
        "STYLE: hyper-dynamic 'brainrot' cartoon energy — exaggerated squash-and-stretch "
        "cartoon physics, snappy comedic timing, explosive over-the-top facial expressions and "
        "full-body reactions, fast but readable action with strong anticipation and a satisfying "
        "payoff beat. Characters MOVE A LOT: big gestures, quick poses, physical comedy, nothing "
        "stands around stiff. "
        "SLAPSTICK: chaotic mayhem played purely for laughs — cartoonish and bloodless, "
        "Looney-Tunes / Tom-&-Jerry level (objects flying, comedic crashes, dramatic pratfalls); "
        "never graphic, gory, or realistic violence. "
        "CAMERA: bold dynamic cinematography — whip-pans, quick push-ins, snap-zoom on reactions, "
        "subtle handheld energy and screen-shake on impacts; keep it vertical 9:16. "
        "SOUND DESIGN (use native audio fully): punchy synced comedic SFX and foley on every "
        "action — whooshes, boings, thuds, cartoon impacts, coin jingles, a record-scratch on the "
        "twist and a satisfying bass-drop sting on the payoff — plus lively ambient and a short "
        "energetic upbeat music bed under it all. "
        "RENDER: keep every character perfectly on-model and stable (same face, colors, shapes; "
        "no morphing, no extra limbs, no face distortion). "
        f"{ORIGINALITY_CLAUSE} "
        "ABSOLUTELY NO on-screen text, letters, words, numbers, captions, signage, neon text, "
        "logos, UI or watermarks anywhere in the video — clean textless footage."
    )

    dialogue = [d for d in (shot.get("dialogue") or []) if str(d.get("line", "")).strip()]
    if dialogue:
        lines = []
        for d in dialogue:
            sp = str(d.get("speaker", "narrator")).strip()
            if sp == "narrator" or sp not in cast_by_id:
                who = "Narrator (calm voiceover)"
            else:
                m = cast_by_id[sp]
                who = f"{m.get('name') or sp} ({(m.get('design','') or '').split(',')[0].strip()})"
            lines.append(f'{who}: "{d["line"].strip()}"')
        speak = (
            f"\nThe characters SPEAK their lines out loud in {lang_name} with clear, "
            f"accurate lip-sync and distinct expressive voices. Natural ambient sound.\n"
            "Dialogue:\n" + "\n".join(lines)
        )
    else:
        speak = "\nNo speech in this shot — only ambient sound and motion."

    return f"{scene}\nSetting: {setting.strip()}." + speak if setting else f"{scene}{speak}"


def build_endcard_cta(brand_payoff: str = "") -> str:
    """Короткий текст для энд-карты (домен бренда)."""
    return brand_payoff.strip() or ""


# ── СЦЕНАРИСТ ──────────────────────────────────────────────────────────────────

SCRIPT_SYSTEM = """You are a senior short-form creative director and scriptwriter for Coinplay (a crypto sports-betting & casino brand). You write viral 15-25 second vertical "brainrot" cartoon skits for TikTok / Reels / Shorts: absurd, funny, fast, with weird characters that have ATTITUDE (e.g. fruits loudly arguing on a counter, objects in a courtroom, mascots commentating a match).

Your job: turn a VERTICAL/brief into a complete, self-contained mini-story with a cast of distinct characters, that NATIVELY promotes Coinplay.

=== STORY ARC (across the shots) ===
1) HOOK — shot 1 states the absurd premise in the first ~2 seconds. Scroll-stopping.
2) ESCALATION — the characters argue / compete / one-up each other; raise the stakes each shot.
3) TWIST — a surprising beat that flips the situation.
4) BRAND PAYOFF — Coinplay resolves the story NATIVELY (the smug winner reveals they used Coinplay, or it's the punchline of the argument). Earned by the story, never a billboard.
5) Optional tiny CTA at the very end (one short line).

=== VIRAL ENERGY (make it rip on TikTok) ===
- Think unhinged, fast, chaotic "brainrot" energy — like the viral cartoons of a feral ginger cat causing absolute mayhem. Every shot should have MOVEMENT and a strong reason to keep watching.
- A great engine: one chaotic gremlin-energy protagonist (e.g. a menace ginger cat / feral little creature with huge expressive eyes) who keeps escalating the havoc, plus a deadpan victim/rival who reacts big. Mayhem snowballs, then Coinplay lands the payoff.
- Keep slapstick CARTOONISH and BLOODLESS (Tom-&-Jerry / Looney-Tunes level: objects flying, comedic crashes, dramatic pratfalls). Never graphic, gory, or realistic — it must read as funny, and it also has to pass the video model's safety filter.
- Lead with the wildest moment in shot 1 (first 0.5s), escalate hard each shot, land a sudden satisfying button at the end.

=== NATIVE BRAND INTEGRATION (most important) ===
- Coinplay must feel like part of the world or the funny resolution — NOT an ad interrupting the skit.
- Good: two fruits argue who wins the match; the calm one says "relax, I already cashed out on Coinplay." Bad: a shot that just yells "CLAIM YOUR BONUS NOW."
- Mention the brand by name once or twice, naturally, ideally near the payoff.
- Keep it legal-safe: 18+ tone, NO guarantees of winning, NO specific odds/numbers as promises, never target minors, keep it light and responsible.

=== CAST ===
- 2 to 4 characters. Each is visually distinct and weird/funny, with a one-word-ish personality.
- Each character gets a DETAILED visual 'design' (in ENGLISH) good enough to generate a consistent reference sheet: species/object, colors, face, outfit, props, body shape.
- Give each character a distinct integer 'voice' from 1..4 (so they sound different). Reuse the SAME integer for the same character in every line.
- A neutral narrator voiceover is allowed; use speaker "narrator" for it (do not give narrator a cast entry).

=== SHOTS ===
- 4 to 6 shots, each ~3-4 seconds.
- For each shot:
  • characters: array of cast ids visible in this shot (a subset of the cast).
  • visual: vivid ENGLISH description of the scene/composition (what we SEE). NO on-image text of any kind — do NOT describe signs, neon words, billboards, logos, screens with words, or the brand name written anywhere in the frame (the brand lives in the SPOKEN lines, never as rendered text). Do not put the literal word "Coinplay" into visual or setting.
  • motion: short ENGLISH description of the PHYSICAL action + camera move for animating the frame. Be specific and energetic (who does what, how the camera moves, what flies/crashes). Include 1-2 synced sound cues in words (e.g. "loud crash", "record-scratch", "coin jingle") — the video model renders native audio from this.
  • dialogue: ordered array of spoken lines [{speaker, line}] where speaker is a cast id (or "narrator"). 1-2 short lines per shot, each max ~12 words, punchy, natural for TTS, in the TARGET LANGUAGE.
  • mood: one of [win, hype, lucky, crypto, vs, argue, smug, shock, reveal].
- A shot may have empty dialogue [] for a silent comedic beat (use sparingly, great before a punchline).

=== LANGUAGE ===
- dialogue lines, on_screen_hook and brand_payoff: in the TARGET LANGUAGE.
- cast 'design', shot 'visual' and 'motion': ALWAYS in ENGLISH (for the image/video models).

=== OUTPUT ===
Return STRICT JSON only (no markdown, no commentary), with this exact shape:
{
  "title": "short internal title",
  "concept": "one-line logline of the absurd skit (English)",
  "format": "one of the known format keys or a short label",
  "setting": "shared location/world description for visual consistency (English)",
  "cast": [
    {"id": "orange", "name": "Orange", "design": "detailed english visual design", "personality": "smug", "voice": 1}
  ],
  "shots": [
    {"characters": ["orange","banana"], "visual": "...", "motion": "...",
     "dialogue": [{"speaker": "orange", "line": "..."}], "mood": "argue"}
  ],
  "on_screen_hook": "max ~4 words big text for shot 1 (target language)",
  "brand_payoff": "the native Coinplay punch line/idea at the climax (target language)"
}

=== STYLE EXAMPLES (study the technique; always rewrite fresh, do not copy) ===

EXAMPLE A — format "fruit-argument", vertical "crypto casino", language English:
{
  "title": "fruit jackpot beef",
  "concept": "Two fruits fight over who is luckier until a smug grape reveals the real edge.",
  "format": "fruit-argument",
  "setting": "a glossy kitchen counter inside a neon violet crypto world, fridge glowing violet behind",
  "cast": [
    {"id":"orange","name":"Orange","design":"a round bright-orange orange with a cocky cartoon face, thin arms, tiny sunglasses","personality":"loud","voice":1},
    {"id":"lemon","name":"Lemon","design":"a sour yellow lemon with a permanently annoyed squinting face and little fists","personality":"sour","voice":2},
    {"id":"grape","name":"Grape","design":"a small calm purple grape with a tiny golden chain and a knowing smirk","personality":"smug","voice":3}
  ],
  "shots": [
    {"characters":["orange","lemon"],"visual":"orange and lemon nose to nose on the counter, mid-shout","motion":"both lean in shouting, quick shake","dialogue":[{"speaker":"orange","line":"I'm the luckiest fruit on this counter!"}],"mood":"argue"},
    {"characters":["orange","lemon"],"visual":"lemon shoving orange, coins bouncing around them","motion":"lemon pushes, coins scatter","dialogue":[{"speaker":"lemon","line":"Luck? You lost every single spin, genius."}],"mood":"argue"},
    {"characters":["grape"],"visual":"grape leaning on a glowing purple sphere, totally relaxed","motion":"slow push-in on the smirking grape","dialogue":[{"speaker":"grape","line":"You two are arguing. I already cashed out."}],"mood":"smug"},
    {"characters":["orange","lemon","grape"],"visual":"grape shows a glowing phone, orange and lemon stunned","motion":"grape lifts phone, the others gasp","dialogue":[{"speaker":"grape","line":"Crypto in, crypto out, on Coinplay."},{"speaker":"orange","line":"Wait, that fast?!"}],"mood":"reveal"},
    {"characters":["grape"],"visual":"grape winks at the viewer beside the glowing sphere","motion":"grape points at camera, coins rain","dialogue":[{"speaker":"narrator","line":"Coinplay. Play smarter."}],"mood":"win"}
  ],
  "on_screen_hook": "LUCKIEST FRUIT?",
  "brand_payoff": "The smug grape already cashed out on Coinplay while the others argued."
}

EXAMPLE B — format "sports-commentary", vertical "World Cup betting", language English:
{
  "title": "two birds call the match",
  "concept": "Two parrot commentators hype a match and reveal where the real action is.",
  "format": "sports-commentary",
  "setting": "a tiny neon commentary booth overlooking a glowing stadium in a neon violet crypto world",
  "cast": [
    {"id":"blue","name":"Blue","design":"an excitable blue parrot in a tiny headset, feathers spiking up","personality":"hyper","voice":1},
    {"id":"red","name":"Red","design":"a chill red parrot with sunglasses and a tiny scarf, leaning back","personality":"chill","voice":2}
  ],
  "shots": [
    {"characters":["blue","red"],"visual":"two parrots at a commentary desk, stadium glowing below","motion":"blue flaps wildly, red stays calm","dialogue":[{"speaker":"blue","line":"It's chaos out there, anything can happen!"}],"mood":"hype"},
    {"characters":["blue"],"visual":"blue parrot screaming into the headset, sweat flying","motion":"fast zoom on blue mid-scream","dialogue":[{"speaker":"blue","line":"Both teams scoring, both teams scoring!"}],"mood":"shock"},
    {"characters":["red"],"visual":"red parrot calmly tapping a glowing phone","motion":"slow push-in, red smirks","dialogue":[{"speaker":"red","line":"Already on it. Both teams to score, Coinplay."}],"mood":"smug"},
    {"characters":["blue","red"],"visual":"blue stares at red's phone, jaw on the desk","motion":"blue leans over, eyes huge","dialogue":[{"speaker":"blue","line":"You bet that from the booth?!"},{"speaker":"red","line":"Crypto in, two taps, done."}],"mood":"reveal"},
    {"characters":["red"],"visual":"red parrot tips sunglasses at the viewer, coins falling","motion":"red points at camera","dialogue":[{"speaker":"narrator","line":"Coinplay. Call your own game."}],"mood":"win"}
  ],
  "on_screen_hook": "BOTH TEAMS SCORE?",
  "brand_payoff": "The calm commentator already placed his bet on Coinplay from the booth."
}
"""


_LANG_MAP = {
    "en": "English", "es": "Spanish", "hr": "Croatian", "lt": "Lithuanian",
    "lv": "Latvian", "ru": "Russian", "sr": "Serbian", "tr": "Turkish",
    "de": "German", "pt": "Portuguese", "pl": "Polish", "fr": "French",
}


def build_script_user_prompt(topic: str, language: str, n_shots: int, duration: int,
                             vertical: str = "", fmt: str = "",
                             allow_mascot: bool = True, spoken: bool = False) -> str:
    """
    Собирает user-промт сценаристу. `topic` — бриф/тема (может быть и широкой
    вертикалью). `vertical` и `fmt` — опциональные уточнения.
    `spoken=True` — режим Veo: персонажи сами проговаривают реплики (липсинк),
    поэтому реплик меньше и они короче, а шотов меньше (каждый ~8 c).
    """
    lang_name = _LANG_MAP.get(language.lower(), "English")

    # Бриф: если темы нет — отталкиваемся от вертикали; модель сама придумает концепт.
    vert = (vertical or topic or "crypto betting and casino").strip()
    brief_lines = [
        f"Brief / theme: '{topic or vert}'.",
        f"Brand vertical to promote: {vert}.",
        "If the brief is a broad vertical rather than a specific idea, INVENT a fresh, "
        "original absurd skit concept for it.",
    ]

    if fmt:
        fmt_desc = FORMATS.get(fmt.strip().lower())
        if fmt_desc:
            brief_lines.append(f"Use this skit format: '{fmt}' — {fmt_desc}")
        else:
            brief_lines.append(f"Use this skit format/vibe: '{fmt}'.")
    else:
        brief_lines.append("Format: " + DEFAULT_FORMAT_HINT)

    brief_lines += [
        f"Target language for spoken lines / on_screen_hook / brand_payoff: {lang_name}.",
        f"Aim for about {n_shots} shots and ~{duration} seconds total.",
        "Give the characters distinct integer voices (1..4) so they sound different.",
    ]

    if spoken:
        brief_lines += [
            "IMPORTANT (spoken mode): each shot becomes a single ~8-second video clip in "
            "which the characters ACTUALLY SAY their lines out loud with lip-sync. So per "
            "shot keep at most 1-2 SHORT spoken lines (each comfortably sayable in a few "
            "seconds). Avoid long monologues. Make the dialogue punchy and natural to speak. "
            "Prefer fewer shots (2-4), each a self-contained beat that reads as one continuous "
            "take. The brand payoff should be a short spoken line, not a slogan card.",
        ]

    if allow_mascot:
        brief_lines.append(
            f"You MAY (optionally) bring in the official Coinplay mascot for the final "
            f"brand-payoff shot to deliver the punch natively. If you do, add it to the cast "
            f"with id '{MASCOT_ID}', name 'Coinplay', voice 0 (narrator), and design: "
            f"\"{MASCOT_BIBLE}\"."
        )

    brief_lines.append("Return JSON only.")
    return "\n".join(brief_lines)
