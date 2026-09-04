"""Simple JSON-based i18n (English / Polish)."""

from __future__ import annotations

import json
from pathlib import Path

_LANG_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, dict[str, str]] = {}
_current = "en"


def available_languages() -> list[tuple[str, str]]:
    return [("en", "English"), ("pl", "Polski")]


def set_language(lang: str) -> None:
    global _current
    code = lang.split("-")[0].lower()
    if code not in ("en", "pl"):
        code = "en"
    _current = code
    _load(code)


def get_language() -> str:
    return _current


def _load(lang: str) -> dict[str, str]:
    if lang in _CACHE:
        return _CACHE[lang]
    path = _LANG_DIR / f"{lang}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    _CACHE[lang] = data
    return data


def t(key: str, **kwargs: object) -> str:
    table = _load(_current)
    fallback = _load("en")
    text = table.get(key) or fallback.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:  # noqa: BLE001
            return text
    return text


# preload
_load("en")
_load("pl")
