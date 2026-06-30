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

# ── ЕДИНЫЙ ВИЗУАЛЬНЫЙ «СКИН» БРЕНДА ─────────────────────────────────────────────
# Применяется ко ВСЕМ роликам поверх любого каста, чтобы мир выглядел «как Coinplay».
BRAND_WORLD = (
    "vibrant stylized 3D cartoon in the Coinplay brand world: deep indigo-to-violet "
    "gradient environment, glossy volumetric purple spheres floating as signature brand "
    "elements, neon magenta and electric-blue rim lighting, golden coin particles and "
    "subtle crypto glyphs drifting in the air, high color saturation, punchy contrast, "
    "playful energetic mood, cinematic yet cartoonish, smooth global illumination, "
    "soft depth of field, Pixar-meets-streetwear render quality"
)

# Композиционные требования под вертикаль 9:16 + крупные вшитые субтитры.
FRAMING_9x16 = (
    "vertical 9:16 composition, characters framed in the central band, generous empty "
    "headroom in the top third and bottom third reserved for large subtitle text, "
    "no on-image text, no captions, no watermark, no logo"
)

# ── ФИРМЕННЫЙ МАСКОТ (опциональное камео в финале) ─────────────────────────────
# Появляется только если включён BRAND_MASCOT_CAMEO — чтобы нативно подать бренд.
MASCOT_BIBLE = (
    "the Coinplay mascot: a sly, confident anthropomorphic fox-like crypto host with "
    "glowing violet eyes, wearing a sleek dark hoodie with a subtle neon-violet Coinplay "
    "'C' emblem, a thin gold chain and oversized headphones around the neck; stylized 3D "
    "cartoon, exaggerated expressive face, big readable eyes, clean bold shapes"
)
MASCOT_ID = "coinplay_host"

# ── НАСТРОЕНИЯ СЦЕНЫ ───────────────────────────────────────────────────────────
SCENE_MOODS = {
    "win":     "explosive jackpot celebration, golden coins raining, confetti, triumphant energy",
    "hype":    "fast hype energy, a character pointing at the viewer, dynamic action lines",
    "lucky":   "slot / roulette spinning, suspense, sparkles, lucky-charm vibe",
    "crypto":  "glowing crypto charts going up, bitcoin and ethereum coins orbiting the scene",
    "vs":      "two characters facing off, duel energy, dramatic stadium lights, tension",
    "argue":   "characters loudly arguing, leaning in, exaggerated angry-funny faces, sweat drops",
    "smug":    "one character calm and smug while another panics, contrast of confidence",
    "shock":   "characters in comedic shock, jaws dropping, big surprised eyes, motion lines",
    "reveal":  "a character pulling back to reveal a giant glowing number or screen",
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
}

DEFAULT_FORMAT_HINT = (
    "pick the single funniest absurd format for this vertical (a great default is two or "
    "three characters loudly arguing, e.g. fruits on a counter)."
)


# ── ПРОМТЫ КАРТИНОК ─────────────────────────────────────────────────────────────

def build_character_ref_prompt(member: dict, setting: str = "") -> str:
    """
    Промт для ОДНОГО референс-листа персонажа (генерится 1 раз на персонажа).
    member: {id, name, design, ...}. Чистый фон-студия — чтобы потом чисто
    переносить персонажа в кейфреймы через мульти-референс.
    """
    name = member.get("name") or member.get("id", "character")
    design = member.get("design", "").strip()
    return (
        f"Full-body character reference sheet of a single character named '{name}'. "
        f"Character design: {design}. "
        f"{BRAND_WORLD}. "
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
            f"{m.get('name') or m.get('id')} ({m.get('design','').strip()})" for m in present
        )
        keep = (
            "Use the provided reference images. Keep EACH of these characters exactly "
            "identical to their reference (same face, colors, shapes, proportions): "
            f"{roster}."
        )
        if len(present) > 1:
            keep += " Place all of them together in the same scene, interacting naturally."
    else:
        keep = "Create the scene described below in the brand world."

    parts = [
        keep,
        f"Scene: {shot.get('visual','').strip()}.",
        (f"Setting: {setting.strip()}." if setting else ""),
        SCENE_MOODS.get(str(shot.get("mood", "")).lower().strip(), ""),
        BRAND_WORLD + ".",
        "Single cinematic keyframe, the characters are the clear foreground subjects, "
        "expressive cartoon acting. " + FRAMING_9x16 + ".",
    ]
    return " ".join(p for p in parts if p)


def build_motion_prompt(shot: dict) -> str:
    """Промт движения для image-to-video (что оживляем в кадре)."""
    motion = shot.get("motion", "").strip()
    n = len(shot.get("characters") or [])
    ensemble = (
        "the characters talk and gesture expressively at each other, big cartoon acting, "
        if n >= 2 else
        "the character performs the action expressively, "
    )
    base = (
        f"Smooth lively cartoon animation: {ensemble}"
        "subtle camera push-in, floating brand spheres drift gently, golden coin particles "
        "shimmer. Keep every character on-model and stable: no morphing, no extra limbs, "
        "no face distortion."
    )
    return f"{motion}. {base}" if motion else base


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
  • visual: vivid ENGLISH description of the scene/composition (what we SEE). No on-image text.
  • motion: short ENGLISH description of the action + camera for animating the frame.
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
  "setting": "a glossy kitchen counter inside the neon Coinplay brand world, fridge glowing violet behind",
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
  "setting": "a tiny neon commentary booth overlooking a glowing stadium in the Coinplay world",
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
                             allow_mascot: bool = True) -> str:
    """
    Собирает user-промт сценаристу. `topic` — бриф/тема (может быть и широкой
    вертикалью). `vertical` и `fmt` — опциональные уточнения.
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

    if allow_mascot:
        brief_lines.append(
            f"You MAY (optionally) bring in the official Coinplay mascot for the final "
            f"brand-payoff shot to deliver the punch natively. If you do, add it to the cast "
            f"with id '{MASCOT_ID}', name 'Coinplay', voice 0 (narrator), and design: "
            f"\"{MASCOT_BIBLE}\"."
        )

    brief_lines.append("Return JSON only.")
    return "\n".join(brief_lines)
