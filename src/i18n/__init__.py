"""Translation layer.

The English source string is the key, so an untranslated string simply falls
through unchanged. New English text coming from upstream therefore keeps
working without touching this package.
"""

from i18n.ru import RU

__all__ = ["DEFAULT_LANGUAGE", "LANGUAGE_NAMES", "get_language", "set_language", "t"]

DEFAULT_LANGUAGE = "ru"

# An empty dictionary means "use the source strings as they are".
_CATALOGS: dict[str, dict[str, str]] = {
    "en": {},
    "ru": RU,
}

LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Русский",
}

_current_language = DEFAULT_LANGUAGE


def get_language() -> str:
    return _current_language


def set_language(language: str) -> None:
    global _current_language
    _current_language = language if language in _CATALOGS else DEFAULT_LANGUAGE


def t(text: str) -> str:
    """Translate a source string into the current language."""
    return _CATALOGS[_current_language].get(text, text)
