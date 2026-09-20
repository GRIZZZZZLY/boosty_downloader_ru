import ast
import pathlib
import re
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from i18n import DEFAULT_LANGUAGE, get_language, set_language, t  # noqa: E402
from i18n.ru import RU  # noqa: E402

PLACEHOLDER = re.compile(r"\{(\w+)\}")


@pytest.fixture(autouse=True)
def restore_language():
    yield
    set_language(DEFAULT_LANGUAGE)


def test_default_language_is_russian():
    assert get_language() == "ru"


def test_translates_known_string():
    set_language("ru")
    assert t("Settings") == "Настройки"


def test_english_returns_the_source_string():
    set_language("en")
    assert t("Settings") == "Settings"


def test_unknown_string_passes_through():
    """A new string from upstream must keep working before it is translated."""
    set_language("ru")
    assert t("Brand new upstream string") == "Brand new upstream string"


def test_unknown_language_falls_back_to_the_default():
    set_language("klingon")
    assert get_language() == DEFAULT_LANGUAGE


def test_placeholders_match_the_source_string():
    """A renamed placeholder would raise KeyError at format() time."""
    mismatched = {
        source: translation
        for source, translation in RU.items()
        if set(PLACEHOLDER.findall(source)) != set(PLACEHOLDER.findall(translation))
    }
    assert mismatched == {}


def _translated_literals():
    for path in SRC.rglob("*.py"):
        if path.parts[-2] == "i18n":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                yield path.relative_to(SRC), node.args[0].value


def test_every_translated_literal_has_a_russian_entry():
    missing = sorted({text for _, text in _translated_literals() if text not in RU})
    assert missing == []
