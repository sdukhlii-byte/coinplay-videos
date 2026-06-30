"""
pipeline/script_writer.py — генерация сюжетного сценария ролика через OpenAI.

НОВАЯ схема (мультиперсонажный скит, story-driven):

{
  "title":  "...",
  "concept": "одно-два предложения идеи",
  "format": "fruit-argument | courtroom | ...",   # опц.
  "setting": "english description of the place/scene",
  "cast": [
    {"id":"lemon","name":"Lemon","design":"ENGLISH visual bible",
     "personality":"...", "voice":1}
  ],
  "shots": [
    {"characters":["lemon","lime"],
     "visual":"ENGLISH keyframe description",
     "motion":"ENGLISH camera/character motion",
     "dialogue":[{"speaker":"lemon","line":"реплика на языке ролика"}],
     "mood":"argue"}
  ],
  "on_screen_hook": "крупный текст-хук (язык ролика)",
  "brand_payoff": "нативная брендовая реплика-вывод (язык ролика)"
}

Модуль делает не только запрос к LLM, но и ЖЁСТКУЮ нормализацию ответа
(`_coerce`), чтобы дальше по конвейеру гарантированно пришла валидная структура:
у каждого персонажа есть id/design/голос, у каждого шота — visual/motion,
реплики привязаны к существующим персонажам, голоса не конфликтуют.

Поддержана обратная совместимость со старым форматом (shots[].narration без cast):
такой сценарий превращается в ролик «один рассказчик».
"""

from __future__ import annotations

import json
import time
import logging

import config as C
from brand.brand_prompts import (
    SCRIPT_SYSTEM,
    build_script_user_prompt,
    MASCOT_ID,
)

log = logging.getLogger("script")

# Клиент OpenAI создаём ЛЕНИВО (внутри write_script), чтобы модуль можно было
# импортировать без установленного пакета openai — для офлайн-инструментов
# (CLI storyboard, нормализация Script_Override, тесты), которым LLM не нужен.
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=C.OPENAI_API_KEY)
    return _client

_MAX_CAST = 4          # 1..4 «обычных» персонажей (+ маскот = голос 0)
_VOICE_POOL = [1, 2, 3, 4]


# ── НОРМАЛИЗАЦИЯ ───────────────────────────────────────────────────────────────

def _slug(s: str, fallback: str) -> str:
    s = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(s).strip().lower())
    s = "_".join(p for p in s.split("_") if p)
    return s or fallback


def _coerce_cast(data: dict) -> list[dict]:
    """
    Приводит cast к списку валидных персонажей. Гарантирует уникальные id,
    наличие design, распределяет неконфликтующие голоса (маскот → 0, прочие → 1..4).
    """
    raw = data.get("cast")
    cast: list[dict] = []

    # Back-compat: сценарий без cast (старый формат narration) → один рассказчик.
    if not isinstance(raw, list) or not raw:
        log.info("Script has no cast — narrator-only (legacy) mode")
        return []

    seen_ids: set[str] = set()
    for i, m in enumerate(raw):
        if not isinstance(m, dict):
            continue
        cid = _slug(m.get("id") or m.get("name") or f"char{i+1}", f"char{i+1}")
        base = cid
        k = 2
        while cid in seen_ids:
            cid = f"{base}_{k}"
            k += 1
        seen_ids.add(cid)

        name = str(m.get("name") or cid.replace("_", " ").title()).strip()
        design = str(m.get("design") or "").strip()
        if not design:
            design = (f"a bold stylized cartoon character representing '{name}', "
                      f"thick clean outlines, saturated colors, expressive face")
            log.warning("Cast '%s' had no design — synthesized a fallback", cid)
        personality = str(m.get("personality") or "").strip()

        voice_raw = m.get("voice")
        try:
            voice = int(voice_raw)
        except (TypeError, ValueError):
            voice = None

        cast.append({
            "id": cid, "name": name, "design": design,
            "personality": personality, "voice": voice,
        })

    # Маскот всегда говорит голосом рассказчика (0).
    for m in cast:
        if m["id"] == MASCOT_ID:
            m["voice"] = 0

    # Раздаём непротиворечивые голоса 1..4 для не-маскотов.
    pool = list(_VOICE_POOL)
    used = {m["voice"] for m in cast if m["id"] != MASCOT_ID and m["voice"] in pool}
    free = [v for v in pool if v not in used]
    for m in cast:
        if m["id"] == MASCOT_ID:
            continue
        if m["voice"] not in pool:
            m["voice"] = free.pop(0) if free else ((max(used) % 4) + 1 if used else 1)
            used.add(m["voice"])

    # Не больше _MAX_CAST не-маскотов (отрезаем хвост, чтобы не раздувать стоимость).
    non_mascot = [m for m in cast if m["id"] != MASCOT_ID]
    mascot = [m for m in cast if m["id"] == MASCOT_ID]
    if len(non_mascot) > _MAX_CAST:
        log.warning("Cast too large (%d) — trimming to %d (+mascot)", len(non_mascot), _MAX_CAST)
        non_mascot = non_mascot[:_MAX_CAST]
    cast = non_mascot + mascot
    return cast


def _coerce_shots(data: dict, cast_ids: list[str]) -> list[dict]:
    raw = data.get("shots")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"script missing shots: {str(data)[:200]}")

    mascot_present = MASCOT_ID in cast_ids
    default_chars = [c for c in cast_ids if c != MASCOT_ID] or list(cast_ids)

    shots: list[dict] = []
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            continue

        visual = str(s.get("visual") or "").strip()
        if not visual:
            # Без визуала кадр не нарисовать — синтезируем минимальный из мудборда.
            visual = f"the characters in the scene, dynamic vertical composition, shot {i+1}"
            log.warning("Shot %d had no visual — synthesized a fallback", i)
        motion = str(s.get("motion") or "").strip() or "subtle handheld camera, lively idle motion"
        mood = str(s.get("mood") or "hype").strip().lower()

        # characters ⊆ cast; иначе дефолт.
        chars = s.get("characters")
        if isinstance(chars, list):
            chars = [_slug(c, "") for c in chars]
            chars = [c for c in chars if c in cast_ids]
        else:
            chars = []
        if not chars:
            chars = list(default_chars)

        # dialogue: новый формат [{speaker,line}] ИЛИ legacy narration (строка).
        dialogue = s.get("dialogue")
        coerced: list[dict] = []
        if isinstance(dialogue, list):
            for d in dialogue:
                if not isinstance(d, dict):
                    continue
                line = str(d.get("line") or "").strip()
                if not line:
                    continue
                sp = _slug(d.get("speaker") or "narrator", "narrator")
                if sp != "narrator" and sp not in cast_ids:
                    sp = "narrator"
                coerced.append({"speaker": sp, "line": line})
        elif s.get("narration"):
            # Legacy: одна закадровая строка → рассказчик.
            coerced.append({"speaker": "narrator", "line": str(s["narration"]).strip()})
        # пустой dialogue [] допустим — «немой» бит.

        shots.append({
            "characters": chars,
            "visual": visual,
            "motion": motion,
            "dialogue": coerced,
            "mood": mood,
        })

    if not shots:
        raise ValueError("script shots became empty after coercion")
    return shots


def _coerce(data: dict) -> dict:
    cast = _coerce_cast(data)
    cast_ids = [m["id"] for m in cast]
    shots = _coerce_shots(data, cast_ids)

    out = {
        "title": str(data.get("title") or "coinplay short").strip(),
        "concept": str(data.get("concept") or "").strip(),
        "format": str(data.get("format") or "").strip(),
        "setting": str(data.get("setting") or "").strip(),
        "cast": cast,
        "shots": shots,
        "on_screen_hook": str(data.get("on_screen_hook") or "").strip(),
        "brand_payoff": str(data.get("brand_payoff") or "").strip(),
    }
    return out


# ── ЗАПРОС К LLM ───────────────────────────────────────────────────────────────

def write_script(topic: str, language: str, n_shots: int, duration: int,
                 vertical: str = "", fmt: str = "", allow_mascot: bool = True,
                 retries: int = 3) -> dict:
    """
    Генерит сюжетный мультиперсонажный сценарий и нормализует его до валидной схемы.
    `vertical` и `fmt` — необязательные уточнения (вертикаль/формат скита).
    """
    user = build_script_user_prompt(
        topic, language, n_shots, duration,
        vertical=vertical, fmt=fmt, allow_mascot=allow_mascot,
    )
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = _get_client().chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SCRIPT_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.95,
                max_tokens=1600,            # каста + диалоги крупнее старого формата
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            data = _coerce(json.loads(raw))
            log.info("Script ok: '%s' cast=%d shots=%d fmt=%s",
                     data["title"], len(data["cast"]), len(data["shots"]),
                     data["format"] or "-")
            return data
        except Exception as e:
            last_err = e
            log.warning("write_script attempt %d/%d: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"write_script failed after all retries: {last_err}")


def coerce_external(data: dict) -> dict:
    """Публичная нормализация для Script_Override / CLI (готовый JSON от пользователя)."""
    return _coerce(data)
