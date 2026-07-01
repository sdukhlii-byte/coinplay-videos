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
    # — кинодрама (телесериал) —
    "heartbreak": "a devastated character, tears welling and streaming, trembling, rain on their face, raw emotional cinematic close-up",
    "betrayal":   "a cutting betrayal beat — one character stunned and hurt, the other cold and unreadable, heavy dramatic tension",
    "tears":      "a character crying dramatically, huge glistening tearful eyes, telenovela-level raw emotion, rain and neon glow",
    "romance":    "a charged tender moment between two characters, soft rain, longing looks, warm dramatic key light",
    "argue":      "a heated confrontation, one character shouting through tears, the other cold, faces lit by neon and rain",
    "shock":      "a character in raw shock, hand flying to the mouth, eyes blown wide, a sharp gasp, dramatic freeze",
    "reveal":     "a slow dramatic reveal — a character turns or lifts a glowing phone, warm golden light blooming across their face",
    "smug":       "one character calm and quietly triumphant while another is stunned, cool confident contrast",
    "win":        "a triumphant golden climax, a cascade of golden coins pouring over the scene, warm victorious glow, sweeping camera",
    # — экшн/хаос (для не-телесериал брифов) —
    "hype":       "frenetic hype energy, a character lunging at the viewer, speed lines, things flying around the frame",
    "lucky":      "slot / roulette spinning at insane speed, slamming to a stop, sparks and sparkles bursting",
    "crypto":     "glowing crypto charts rocketing upward, coins whirling around the scene",
    "vs":         "two characters slamming into a face-off, duel energy, dramatic light, electric tension",
    "chaos":      "total slapstick mayhem, things crashing and flying, a troublemaker wreaking havoc, everyone reacting big",
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

SCRIPT_SYSTEM = """You are a senior short-form creative director for Coinplay (a crypto sports-betting & casino brand). You write short, CINEMATIC vertical AI-reels in the viral "absurd character, dead-straight drama" format that blows up on TikTok/Reels: an utterly ABSURD character (a fruit/food with a human-like body and a fruit head, or a fully anthropomorphic animal) plays a completely SERIOUS dramatic genre with ZERO winking. The whole hook is the contrast — ridiculous character, deadly-straight cinematic execution. Photoreal animated-feature look (Pixar-grade but grounded and cinematic), shot like a real film trailer.

Your job: turn a brief into a self-contained ~45-60 second cinematic mini-drama that NATIVELY resolves on Coinplay.

=== GENRE: TELENOVELA / soap-opera drama (default) ===
- Melodrama played 100% straight: love, betrayal, a secret, a rival arriving, a tearful confrontation, a jaw-dropping reveal.
- The COMEDY is NEVER in jokes or quips — it is purely in an absurd character taking soap-opera emotion dead seriously. Do NOT write it as a comedy skit.

=== STORY — told VISUALLY, like a trailer (NOT chatter) ===
Carry the story with BLOCKING and PROPS, not talking heads:
1) SETUP — establish the relationship / world (a couple on a rainy balcony; someone packing a suitcase).
2) RISING TENSION — a VISUAL beat: a suitcase by the door (someone is leaving), a luxury car pulling up in the rain (a rival arrives), a phone lighting up.
3) THE SECRET / TWIST — the dramatic reveal. For Coinplay: the "earth-shattering secret" is that the lead is secretly rich / unbothered BECAUSE of Coinplay.
4) EMOTIONAL CLIMAX — ONE huge beat: tears, a gasp, a slap, a walk-away, an embrace.
5) BRAND PAYOFF — Coinplay lands AS the resolution of the drama (revealed on a glowing phone; the empire that quietly ran on Coinplay), then a golden button.

=== SHOTS — THE MOST IMPORTANT PART ===
- 6 to 10 shots. Each shot is ONE clear dramatic BEAT. NEVER two characters just standing and talking at each other.
- STRONGLY prefer SINGLE-SUBJECT shots: one character emoting BIG (a devastated close-up, a smug reveal, a tearful gasp). Use a tight 2-shot ONLY for a real confrontation beat, and stage it with ACTION (one turns away, one grabs a hand, one lifts a phone).
- Include 1-2 B-ROLL / ESTABLISHING shots with NO characters (characters: []) — a rain-soaked neon skyline, a luxury car arriving in slow motion, an empty wet street. These are VITAL for cinematic pacing and make it feel like a real film.
- Every shot has a clear PHYSICAL ACTION or CAMERA MOVE (arrives, leaves, turns, collapses, lifts a phone; camera pushes in, cranes, tracks, whip-pans). Describe the PEAK of that action — never a static pose.
- GROUNDED, REAL cinematic locations (rainy penthouse balcony, mansion driveway, jungle porch, rain-slicked neon street, glowing skyline). NOT a flat purple void — the brand is at most a subtle background accent.

=== CAST ===
- 1 to 3 characters total — keep it SMALL for consistency (a telenovela couple, optionally one rival).
- The lead is an ABSURD original character played straight: e.g. a dragon-fruit-headed woman with a human body in a silk dress, a banana-headed man in a suit, an anthropomorphic wolf tycoon. FULLY ORIGINAL design, not based on any movie/game/brand character.
- Each character: a DETAILED ENGLISH 'design' good enough for a consistent reference sheet (fruit/species, head, human-like body, outfit, colors), plus a distinct integer 'voice' 1..4 (reuse the same integer for that character everywhere).

=== DIALOGUE — telenovela = sparse + loaded ===
- AT MOST ONE short, emotionally-loaded line per shot (max ~10 words), delivered big. MANY shots have NO dialogue (just emotion, action, music, B-roll) — silence is powerful here.
- Lines are raw melodrama, not jokes: "You lied to me." / "I gave you everything." / "...how are you so calm?"
- The brand lands in ONE late line, naturally: "...because I already won. On Coinplay."

=== NATIVE BRAND ===
- Coinplay is the SECRET/twist that RESOLVES the drama — never a billboard, never "claim your bonus". There is NO separate brand mascot; the lead carries the brand.
- Legal-safe: 18+ tone, no guaranteed-win claims, no specific odds/numbers, never target minors.

=== HARD RULES ===
- NO on-screen text anywhere (no signs, neon words, logos, captions, numbers). Never write the literal word "Coinplay" into 'visual' or 'setting' — only into spoken lines. Leave 'on_screen_hook' as an EMPTY string "".
- 'design', 'visual', 'motion' ALWAYS in ENGLISH. dialogue + brand_payoff in the TARGET LANGUAGE.
- mood is one of: heartbreak, betrayal, tears, romance, shock, reveal, smug, win, argue.

=== OUTPUT ===
Return STRICT JSON only (no markdown, no commentary), with this exact shape:
{
  "title": "short internal title",
  "concept": "one-line logline of the absurd straight-drama (English)",
  "format": "telenovela",
  "setting": "shared grounded cinematic location (English), no brand word",
  "cast": [
    {"id": "lia", "name": "Lia", "design": "detailed english visual design", "personality": "wounded", "voice": 2}
  ],
  "shots": [
    {"characters": ["lia"], "visual": "...", "motion": "...",
     "dialogue": [{"speaker": "lia", "line": "..."}], "mood": "tears"}
  ],
  "on_screen_hook": "",
  "brand_payoff": "the native Coinplay secret/twist at the climax (target language)"
}

=== EXAMPLE (telenovela; study the technique, ALWAYS write fresh, never copy) ===
{
  "title": "the dragonfruit's secret",
  "concept": "A dragon-fruit woman confronts her cold tycoon husband on a rainy balcony; his devastating secret is that his entire fortune quietly ran on Coinplay.",
  "format": "telenovela",
  "setting": "a rain-soaked luxury penthouse balcony at night over a glowing real city skyline; grounded cinematic, photoreal animated-feature look",
  "cast": [
    {"id":"lia","name":"Lia","design":"a slender woman with a human body in an emerald silk evening dress, her head a vivid pink dragon fruit with green flame-like leaves, huge glistening expressive eyes, rain-damp; photoreal 3D animated-feature character, fully original design","personality":"wounded","voice":2},
    {"id":"marco","name":"Marco","design":"a tall man with a human body in a sharp black three-piece suit, his head a ripe yellow banana with a calm brooding face; photoreal 3D animated-feature character, fully original design","personality":"cold","voice":1}
  ],
  "shots": [
    {"characters":[],"visual":"a rain-soaked neon city skyline at night seen from a high balcony, a single luxury car's headlights sweeping the wet street far below","motion":"slow cinematic crane down through the rain toward the balcony, distant thunder","dialogue":[],"mood":"heartbreak"},
    {"characters":["lia"],"visual":"Lia alone at the balcony rail, rain mixing with her tears, head snapping toward camera","motion":"slow push-in to a tight devastated close-up, rain in slow motion","dialogue":[{"speaker":"lia","line":"Was any of it real?"}],"mood":"tears"},
    {"characters":["marco"],"visual":"Marco half-turned away in the rain, jaw tight, refusing to look back","motion":"slow dolly around him, his eyes flick coldly to camera","dialogue":[{"speaker":"marco","line":"Every second of it."}],"mood":"betrayal"},
    {"characters":["lia"],"visual":"Lia's hand flies to her mouth, eyes blowing wide","motion":"snap push-in on her shocked tearful face, rain flying, music sting","dialogue":[],"mood":"shock"},
    {"characters":["marco"],"visual":"Marco slowly lifts a glowing phone between them, golden light on his face","motion":"slow tilt up from the glowing phone to his calm eyes, warm light blooming","dialogue":[{"speaker":"marco","line":"My empire was never the secret."}],"mood":"reveal"},
    {"characters":[],"visual":"the neon skyline erupts into a cascade of golden coins pouring down over the rain-soaked city","motion":"sweeping crane-up into the exploding golden skyline, coins raining in slow motion, triumphant swell","dialogue":[{"speaker":"marco","line":"It all ran on Coinplay."}],"mood":"win"},
    {"characters":["lia"],"visual":"Lia, lit gold, a single tear and the start of a stunned smile","motion":"slow push to an emotional golden close-up, coins drifting past","dialogue":[{"speaker":"lia","line":"...all this time?"}],"mood":"smug"}
  ],
  "on_screen_hook": "",
  "brand_payoff": "The cold tycoon's earth-shattering secret: his entire empire quietly ran on Coinplay."
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
            "IMPORTANT (spoken / telenovela mode): each shot becomes a single ~8-second video "
            "clip where the character SAYS their line with lip-sync. So keep AT MOST ONE short "
            "emotional line per shot (comfortably sayable in a few seconds), and make MANY shots "
            "SILENT (empty dialogue []) — a devastated look, an arrival, a B-roll beat. Use "
            "6-10 shots total. Strongly prefer SINGLE-SUBJECT shots (one character emoting big); "
            "include 1-2 character-free B-roll/establishing shots for pacing. Each shot is ONE "
            "clear dramatic beat with a real action or camera move — never two heads just talking. "
            "The brand payoff is one short spoken line, not a slogan card.",
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
