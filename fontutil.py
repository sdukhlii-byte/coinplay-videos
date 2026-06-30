"""
fontutil.py — крошечный самодостаточный ресолвер шрифтов (без внешних зависимостей).

Зачем: libass матчит шрифт по ВНУТРЕННЕМУ family name из таблицы `name`, а не по
имени файла. Если в репо лежит битый файл (например, скачанная HTML-страница 404
вместо .ttf) или вес помечен неверно, субтитры молча падают на системный DejaVu —
бренд-шрифт не применяется, и это не видно в логах.

Этот модуль:
  • проверяет, что файл — действительно sfnt-шрифт (по сигнатуре),
  • читает реальный family name прямо из таблицы `name`,
  • выбирает первый рабочий шрифт из списка кандидатов.

Парсер `name` минимальный, но корректный для одиночных TTF/OTF (TrueType/OpenType).
"""

from __future__ import annotations

import struct
import logging

log = logging.getLogger("fontutil")

_SFNT_MAGIC = {b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"}


def is_font_file(path: str) -> bool:
    """True, если файл начинается с валидной sfnt-сигнатуры (а не HTML/мусора)."""
    try:
        with open(path, "rb") as f:
            return f.read(4) in _SFNT_MAGIC
    except OSError:
        return False


def _decode_name(platform_id: int, data: bytes) -> str:
    # Windows (3) и Unicode (0) → UTF-16BE; Macintosh (1) → latin-1.
    if platform_id in (0, 3):
        try:
            return data.decode("utf-16-be").strip()
        except UnicodeDecodeError:
            return data.decode("latin-1", "ignore").strip()
    return data.decode("latin-1", "ignore").strip()


def family_name(path: str) -> str | None:
    """
    Возвращает family name из таблицы `name` (nameID 16 «typographic family»,
    иначе nameID 1 «family»), или None если прочитать не удалось.
    """
    try:
        with open(path, "rb") as f:
            blob = f.read()
    except OSError:
        return None

    if blob[:4] not in _SFNT_MAGIC:
        return None

    try:
        num_tables = struct.unpack(">H", blob[4:6])[0]
        name_off = name_len = None
        for i in range(num_tables):
            rec = 12 + i * 16
            tag = blob[rec:rec + 4]
            if tag == b"name":
                name_off, name_len = struct.unpack(">II", blob[rec + 8:rec + 16])
                break
        if name_off is None:
            return None

        fmt, count, string_off = struct.unpack(">HHH", blob[name_off:name_off + 6])
        strings_base = name_off + string_off

        # Собираем кандидатов: nameID -> (platform, текст). Предпочитаем 16, потом 1.
        candidates: dict[int, str] = {}
        for j in range(count):
            r = name_off + 6 + j * 12
            (platform_id, _enc, _lang, name_id, length, offset) = struct.unpack(
                ">HHHHHH", blob[r:r + 12]
            )
            if name_id not in (1, 16):
                continue
            raw = blob[strings_base + offset: strings_base + offset + length]
            text = _decode_name(platform_id, raw)
            if text and name_id not in candidates:
                candidates[name_id] = text
        return candidates.get(16) or candidates.get(1)
    except (struct.error, IndexError):
        return None


def resolve_font(candidates: list[str], fallback_family: str = "DejaVu Sans") -> tuple[str, str]:
    """
    Принимает список путей-кандидатов (по приоритету). Возвращает (path, family)
    первого валидного шрифта с реально прочитанным family name.

    Если ни один не валиден — логирует громкую ошибку и возвращает ("", fallback_family),
    чтобы libass хотя бы отрендерил системным шрифтом (а не выдал пустые субтитры).
    """
    for path in candidates:
        if not path:
            continue
        fam = family_name(path)
        if fam:
            log.info("Font resolved: %s  (family=%r)", path, fam)
            return path, fam
        if path:  # файл задан, но невалиден — это и есть тот самый скрытый баг
            log.error("Font file is NOT a valid font (broken download?): %s", path)
    log.error("No valid display font found among %s — falling back to %r",
              candidates, fallback_family)
    return "", fallback_family
