"""The post text converter, exercised on three invented posts.

No network and no real post data: every fixture here is built by hand in the
shape the Boosty API returns.
"""

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.boosty.defs import BoostyLinkDto, BoostyListDto, BoostyTextDto  # noqa: E402
from core.draftjs_converter import DraftJsConverter  # noqa: E402


def text(content: str, block_type: str = "unstyled", styles=None) -> BoostyTextDto:
    return BoostyTextDto(
        content=json.dumps([content, block_type, styles or []]), modificator=""
    )


def block_end() -> BoostyTextDto:
    return BoostyTextDto(content="", modificator="BLOCK_END")


def list_item(content: str, children=None) -> dict:
    return {
        "data": [{"content": json.dumps([content, "unstyled", []])}],
        "items": children or [],
    }


# --- post one: a heading, a styled paragraph and a link --------------------

POST_WITH_STYLES = [
    text("Урок 1. Введение", "header-one"),
    block_end(),
    text("Смотрим внимательно", styles=[[0, 0, 7]]),  # BOLD over "Смотрим"
    block_end(),
    BoostyLinkDto(
        content=json.dumps(["Материалы урока", "unstyled", []]),
        url="https://example.com/files",
    ),
]

# --- post two: a nested list ----------------------------------------------

POST_WITH_LIST = [
    text("Что понадобится", "header-two"),
    block_end(),
    BoostyListDto(
        style="unordered",
        items=[
            list_item(
                "Cinema 4D",
                [{"style": "unordered", "items": [list_item("версия 2024")]}],
            ),
            list_item("Photoshop"),
        ],
    ),
]

# --- post three: a list item with no nested list at all --------------------
# This is the shape that used to crash the plain-text converter.

POST_WITH_BARE_LIST = [
    BoostyListDto(style="unordered", items=[{"data": [{"content": ""}]}]),
]


def test_heading_becomes_a_markdown_heading():
    markdown = DraftJsConverter(POST_WITH_STYLES).to_markdown()
    assert markdown.startswith("# Урок 1. Введение")


def test_bold_run_is_wrapped():
    markdown = DraftJsConverter(POST_WITH_STYLES).to_markdown()
    assert "**Смотрим**" in markdown


def test_link_becomes_a_markdown_link():
    markdown = DraftJsConverter(POST_WITH_STYLES).to_markdown()
    assert "[Материалы урока](https://example.com/files)" in markdown


def test_plain_text_keeps_the_link_address():
    plain = DraftJsConverter(POST_WITH_STYLES).to_plain_text()
    assert "https://example.com/files" in plain
    assert "**" not in plain


def test_nested_list_is_indented():
    markdown = DraftJsConverter(POST_WITH_LIST).to_markdown()
    assert "* Cinema 4D" in markdown
    assert "    * версия 2024" in markdown
    assert "* Photoshop" in markdown


def test_nested_list_in_plain_text():
    plain = DraftJsConverter(POST_WITH_LIST).to_plain_text()
    assert "- Cinema 4D" in plain
    assert "  - версия 2024" in plain


@pytest.mark.parametrize("render", ["to_markdown", "to_plain_text"])
def test_list_item_without_children_does_not_crash(render):
    """A list item may arrive without an 'items' key at all."""
    converter = DraftJsConverter(POST_WITH_BARE_LIST)
    assert isinstance(getattr(converter, render)(), str)


@pytest.mark.parametrize("render", ["to_markdown", "to_plain_text"])
def test_broken_content_is_skipped_not_raised(render):
    converter = DraftJsConverter([BoostyTextDto(content="{not json", modificator="")])
    assert getattr(converter, render)() == ""


@pytest.mark.parametrize("render", ["to_markdown", "to_plain_text"])
def test_empty_post_renders_to_nothing(render):
    assert getattr(DraftJsConverter([]), render)() == ""
