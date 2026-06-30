"""
brand/brand_prompts.py — бренд-библиотека для видео.

Аналог banner brand_prompts.py, но для мультяшного мира Coinplay:
  • CHARACTER_BIBLE   — фикс. описание персонажа-маскота (консистентность между шотами)
  • WORLD_STYLE       — единый визуальный стиль кадров (как _STYLE_DARK у баннеров)
  • SCRIPT_SYSTEM     — system-промт сценариста коротких роликов
  • build_*           — сборщики промтов для кадров/анимации

«Нейрослоп-мультик» залетает за счёт: 1) яркого персонажа-маскота, который
повторяется; 2) резкого хука в первые 2 сек; 3) простого нарратива с панчем;
4) крупных вшитых субтитров. Стиль кадра задаём ЗДЕСЬ, на этапе картинки —
именно картинка определяет «мультяшность», i2v потом просто оживляет.
"""

# ── ПЕРСОНАЖ-МАСКОТ (консистентность) ──────────────────────────────────────────
# Один и тот же текст уходит в генерацию reference-картинки и в каждый кейфрейм.
# Меняйте описание под вашего реального маскота, если он есть.
CHARACTER_BIBLE = (
    "Coinplay mascot: a charismatic cartoon character — a sly, confident anthropomorphic "
    "fox-like crypto trader with glowing violet eyes, wearing a sleek dark hoodie with a "
    "subtle neon-violet Coinplay 'C' emblem, a thin gold chain, and oversized headphones around the neck. "
    "Stylized 3D cartoon look (Pixar-meets-streetwear), exaggerated expressive face, big readable eyes, "
    "clean bold shapes, smooth rounded forms. Consistent character across all shots: same outfit, "
    "same proportions, same color palette."
)

# ── ЕДИНЫЙ СТИЛЬ МИРА ──────────────────────────────────────────────────────────
WORLD_STYLE = (
    "vibrant stylized 3D cartoon, Coinplay brand world: deep indigo-to-violet gradient backgrounds, "
    "glossy volumetric purple spheres floating as signature brand elements (like the banners), "
    "neon magenta and electric-blue rim lighting, golden coin particles and crypto glyphs floating, "
    "high saturation, punchy contrast, playful energetic mood, cinematic but cartoonish, "
    "smooth global illumination, soft depth of field, 9:16 vertical composition with the character "
    "centered and clear headroom at top and bottom for big subtitle text, "
    "no on-image text, no watermark, no logo"
)

# Категории/настроения сцены — расширяемо, как у баннеров.
SCENE_MOODS = {
    "win":      "explosive jackpot celebration, golden coins raining, confetti, triumphant pose",
    "hype":     "fast hype energy, character pointing at the viewer, dynamic action lines",
    "lucky":    "slot machine / roulette spinning, suspense, sparkles, lucky-charm vibe",
    "crypto":   "glowing crypto charts going up, bitcoin and ethereum coins orbiting the character",
    "vs":       "two characters facing off, sports-betting duel energy, stadium lights",
    "reveal":   "character pulling back a curtain to reveal a giant bonus number",
}


# ── ПРОМТЫ КАДРОВ ──────────────────────────────────────────────────────────────

def build_character_prompt() -> str:
    """Промт для одного reference-изображения персонажа (генерится 1 раз на ролик)."""
    return (
        f"Full-body hero character sheet, single character on a clean dark violet studio background. "
        f"{CHARACTER_BIBLE} {WORLD_STYLE}. "
        f"Neutral confident standing pose, front view, full body visible, sharp focus, high detail. "
        f"This is a reference sheet to keep the character identical in later scenes."
    )


def build_keyframe_prompt(shot_visual: str, mood: str = "") -> str:
    """Промт для кейфрейма конкретного шота. Передаётся вместе с reference-картинкой."""
    mood_txt = SCENE_MOODS.get(mood.lower().strip(), "")
    parts = [
        "Keep this exact character identical (same face, outfit, colors, proportions).",
        f"Scene: {shot_visual}.",
        mood_txt,
        WORLD_STYLE,
        "single keyframe, the character is the clear foreground subject, vertical 9:16, "
        "leave clear empty space at the top third and bottom third for large subtitle text.",
    ]
    return " ".join(p for p in parts if p)


def build_motion_prompt(shot_motion: str) -> str:
    """Промт движения для image-to-video (что оживляем в кадре)."""
    base = (
        "Smooth lively cartoon animation, the character performs the action naturally, "
        "subtle camera push-in, floating brand spheres drift gently, coin particles shimmer. "
        "Keep the character on-model and stable, no morphing, no extra limbs."
    )
    return f"{shot_motion}. {base}" if shot_motion else base


# ── СЦЕНАРИСТ ──────────────────────────────────────────────────────────────────

SCRIPT_SYSTEM = """You are a senior short-form video scriptwriter for Coinplay.com — a crypto sports betting & casino brand.
You write punchy 15-20 second vertical cartoon skits ("brainrot" style) for Reels / Shorts / TikTok, starring the Coinplay mascot.

Hard rules:
- Output STRICT JSON only. No markdown, no commentary.
- The video has N shots (you'll be told N). Each shot ~3-4 seconds.
- Shot 1 MUST be a scroll-stopping hook in the first 2 seconds.
- The last shot MUST deliver a clear CTA toward Coinplay (e.g. claim bonus / join / play).
- narration: ONE short spoken line per shot, max ~12 words, punchy, natural for TTS. This is what the voiceover says.
- visual: a vivid description of WHAT we see in this shot's frame (the mascot + scene). No text in the image.
- motion: short description of the ACTION/camera for animating that frame.
- mood: one of [win, hype, lucky, crypto, vs, reveal] that best fits the shot.
- Keep it legal-safe: no guarantees of winning, no targeting minors, add nothing about specific odds.
- Match the requested language for the narration. Keep visual/motion in English (for the image/video models).

Respond ONLY with this JSON shape:
{
  "title": "short internal title",
  "shots": [
    {"visual": "...", "motion": "...", "narration": "...", "mood": "hype"}
  ],
  "on_screen_hook": "max 4 words, big text shown on shot 1 (in the target language)"
}"""


def build_script_user_prompt(topic: str, language: str, n_shots: int, duration: int) -> str:
    lang_map = {
        "en": "English", "es": "Spanish", "hr": "Croatian", "lt": "Lithuanian",
        "lv": "Latvian", "ru": "Russian", "sr": "Serbian", "tr": "Turkish",
    }
    lang_name = lang_map.get(language.lower(), "English")
    return (
        f"Topic / theme: '{topic}'.\n"
        f"Language for narration & on_screen_hook: {lang_name}.\n"
        f"Number of shots: {n_shots}. Target total length: ~{duration} seconds.\n"
        f"Return JSON only."
    )
