#!/usr/bin/env python3
"""
cli.py — локальный инструмент для дешёвой итерации над креативом БЕЗ Airtable.

Подкоманды:
  prompt      Печатает user-промпт, который уйдёт сценаристу (LLM). Полностью офлайн.
  concept     Генерит сценарий (нужен OPENAI_API_KEY) и печатает JSON. → можно
              сохранить и потом отрисовать через `render`.
  storyboard  Берёт готовый сценарий (JSON-файл) и печатает ВСЕ собранные промпты
              (референсы каста, кейфреймы, моушены) + сводку. Офлайн, без API —
              удобно проверять, что и как пойдёт в генерацию картинок/видео.
  render      Берёт сценарий (JSON-файл) и собирает реальный mp4 (нужны все ключи:
              FAL/ELEVENLABS/OPENAI). Пишет файл локально, Airtable/Telegram не трогает.

Примеры:
  python3 cli.py prompt --topic "crypto casino" --vertical "casino" --format fruit-argument --lang en
  python3 cli.py concept --topic "World Cup BTTS" --vertical "sportsbook" --lang hr > script.json
  python3 cli.py storyboard script.json
  python3 cli.py render script.json -o out.mp4
"""

import os
import sys
import json
import argparse

# Чтобы офлайн-подкоманды (prompt/storyboard) не падали на отсутствии секретов,
# подставляем безвредные дефолты ТОЛЬКО если переменных нет (реальные не трогаем).
for _k in ["AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "OPENAI_API_KEY", "FAL_KEY",
           "ELEVENLABS_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
           "ELEVEN_VOICE_ID"]:
    os.environ.setdefault(_k, "x")


def _load_script(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    from pipeline import script_writer
    return script_writer.coerce_external(data)


def cmd_prompt(args):
    from brand.brand_prompts import build_script_user_prompt, SCRIPT_SYSTEM
    user = build_script_user_prompt(
        args.topic, args.lang, args.shots, args.duration,
        vertical=args.vertical, fmt=args.format, allow_mascot=not args.no_mascot,
    )
    print("=== SYSTEM (creative director) ===\n")
    print(SCRIPT_SYSTEM)
    print("\n=== USER (brief) ===\n")
    print(user)


def cmd_concept(args):
    from pipeline import script_writer
    script = script_writer.write_script(
        args.topic, args.lang, args.shots, args.duration,
        vertical=args.vertical, fmt=args.format, allow_mascot=not args.no_mascot,
    )
    print(json.dumps(script, ensure_ascii=False, indent=2))


def cmd_storyboard(args):
    from brand.brand_prompts import (
        build_character_ref_prompt, build_mascot_ref_prompt,
        build_keyframe_prompt, build_motion_prompt, build_veo_prompt, MASCOT_ID,
    )
    import config as C
    script = _load_script(args.script)
    cast = script.get("cast", [])
    cast_by_id = {m["id"]: m for m in cast}
    setting = script.get("setting", "")
    lang = getattr(args, "lang", "en") or "en"

    print(f"# {script.get('title','(no title)')}")
    if script.get("concept"):
        print(f"concept: {script['concept']}")
    print(f"format: {script.get('format') or '-'}   setting: {setting or '-'}")
    print(f"hook:   {script.get('on_screen_hook') or '-'}")
    print(f"payoff: {script.get('brand_payoff') or '-'}")
    print(f"cast ({len(cast)}): " + ", ".join(
        f"{m['id']}[v{m.get('voice')}]" for m in cast) or "narrator-only")

    print("\n=== CHARACTER REFERENCE PROMPTS ===")
    for m in cast:
        prompt = build_mascot_ref_prompt() if m["id"] == MASCOT_ID \
            else build_character_ref_prompt(m, setting)
        print(f"\n--- {m['id']} ({m.get('name')}) ---\n{prompt}")

    print("\n=== SHOTS ===")
    for i, shot in enumerate(script["shots"]):
        print(f"\n--- shot {i} | mood={shot.get('mood')} "
              f"| chars={','.join(shot.get('characters', []))} ---")
        print(f"[keyframe]\n{build_keyframe_prompt(shot, cast_by_id, setting)}")
        if C.VIDEO_ENGINE == "veo":
            print(f"[veo prompt + dialogue]\n{build_veo_prompt(shot, cast_by_id, setting, lang)}")
        else:
            print(f"[motion]\n{build_motion_prompt(shot)}")
        dlg = shot.get("dialogue", [])
        if dlg:
            print("[dialogue]")
            for d in dlg:
                print(f"   {d['speaker']}: {d['line']}")
        else:
            print("[dialogue] (silent beat)")


def cmd_render(args):
    import logging, tempfile
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    import main as app
    script = _load_script(args.script)
    language = args.lang or "en"
    workdir = tempfile.mkdtemp(prefix="cpv_cli_")
    out = os.path.abspath(args.output)
    meta = app._build_video(workdir, script, language, out)
    print(json.dumps({"output": out, **meta}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Coinplay Video Generator — локальный CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--topic", default="crypto betting and casino")
        sp.add_argument("--vertical", default="")
        sp.add_argument("--format", default="")
        sp.add_argument("--lang", default="en")
        sp.add_argument("--shots", type=int, default=5)
        sp.add_argument("--duration", type=int, default=20)
        sp.add_argument("--no-mascot", action="store_true")

    sp = sub.add_parser("prompt", help="печать промптов сценаристу (офлайн)")
    add_common(sp); sp.set_defaults(func=cmd_prompt)

    sp = sub.add_parser("concept", help="сгенерить сценарий через LLM (нужен ключ)")
    add_common(sp); sp.set_defaults(func=cmd_concept)

    sp = sub.add_parser("storyboard", help="печать всех промптов для готового сценария (офлайн)")
    sp.add_argument("script", help="путь к JSON-сценарию")
    sp.add_argument("--lang", default="en")
    sp.set_defaults(func=cmd_storyboard)

    sp = sub.add_parser("render", help="собрать mp4 из готового сценария (нужны ключи)")
    sp.add_argument("script", help="путь к JSON-сценарию")
    sp.add_argument("-o", "--output", default="out.mp4")
    sp.add_argument("--lang", default="en")
    sp.set_defaults(func=cmd_render)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
