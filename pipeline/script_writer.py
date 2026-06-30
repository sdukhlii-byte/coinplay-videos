"""
pipeline/script_writer.py — сценарий ролика через OpenAI.
Возвращает структуру: title, shots[{visual, motion, narration, mood}], on_screen_hook.
"""

import json
import time
import logging

from openai import OpenAI

import config as C
from brand.brand_prompts import SCRIPT_SYSTEM, build_script_user_prompt

log = logging.getLogger("script")
_client = OpenAI(api_key=C.OPENAI_API_KEY)


def _validate(data: dict) -> dict:
    if "shots" not in data or not isinstance(data["shots"], list) or not data["shots"]:
        raise ValueError(f"script missing shots: {str(data)[:200]}")
    for i, s in enumerate(data["shots"]):
        for key in ("visual", "motion", "narration"):
            if not s.get(key):
                raise ValueError(f"shot {i} missing '{key}'")
        s.setdefault("mood", "hype")
    data.setdefault("title", "coinplay short")
    data.setdefault("on_screen_hook", "")
    return data


def write_script(topic: str, language: str, n_shots: int, duration: int,
                 retries: int = 3) -> dict:
    user = build_script_user_prompt(topic, language, n_shots, duration)
    for attempt in range(1, retries + 1):
        try:
            resp = _client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SCRIPT_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.9,
                max_tokens=900,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            data = _validate(json.loads(raw))
            log.info(f"Script ok: '{data['title']}' shots={len(data['shots'])}")
            return data
        except Exception as e:
            log.warning(f"write_script attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError("write_script failed after all retries")
