import sys
from datetime import timedelta
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.naming import (  # noqa: E402
    media_file_name,
    pick_heading,
    post_folder_name,
    sanitize,
    unique_file_name,
)

# 2024-05-18 16:39 Moscow time.
PUBLISH_TIME = 1716039591


def test_folder_name_is_date_then_title():
    assert (
        post_folder_name("Доступ к композиции", PUBLISH_TIME, "some-uuid")
        == "2024-05-18 — Доступ к композиции"
    )


def test_folder_date_uses_moscow_time_not_the_local_clock():
    """22:30 UTC on the 1st is already the 2nd in Moscow."""
    late_evening_utc = 1719872999  # 2024-07-01 21:09 UTC, 2024-07-02 00:09 MSK
    assert post_folder_name("Ночной пост", late_evening_utc, "id").startswith(
        "2024-07-02"
    )


def test_moscow_offset_needs_no_timezone_database():
    """The Python bundled into the built app carries no tzdata.

    Asking zoneinfo for 'Europe/Moscow' there raises at import time and the
    app never starts, so the offset has to be built in.
    """
    import core.naming as naming

    assert naming.POST_TIMEZONE.utcoffset(None) == timedelta(hours=3)
    assert "zoneinfo" not in sys.modules or not hasattr(naming, "ZoneInfo")


def test_folder_name_falls_back_to_the_post_id():
    assert post_folder_name("", PUBLISH_TIME, "abc-123") == "2024-05-18 — abc-123"


def test_long_title_is_cut_on_a_word_boundary():
    title = (
        "Тут вы сможете скачать полностью проект со всеми текстурами и освещением) "
        "Обязательно отпишите, всё ли получилось и что было непонятно"
    )
    name = post_folder_name(title, PUBLISH_TIME, "id")
    body = name.removeprefix("2024-05-18 — ")
    assert len(body) <= 100
    assert not body.endswith(" ")
    # Cut between words, never mid-word.
    assert title.startswith(body)
    assert title[len(body)] == " "


def test_sanitize_removes_characters_windows_refuses():
    assert sanitize('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_collapses_whitespace_and_trailing_dots():
    assert sanitize("  много   пробелов  ...") == "много пробелов"


def test_reserved_windows_name_is_escaped():
    assert sanitize("CON") != "CON"


def test_newline_becomes_a_space_not_nothing():
    """A heading and its description are separated by a newline in one block."""
    assert (
        sanitize("2 Урок.\nКакой продукт выбрать?") == "2 Урок. Какой продукт выбрать"
    )


def test_file_name_keeps_punctuation_where_it_is_cut():
    """Folder names drop a trailing comma; file names keep it, as the dump does."""
    title = (
        "Вы сможете получить доступ ко всей сцене, с настроенным освещением, "
        "текстурами, эмиттером)"
    )
    assert media_file_name(1, [title], extension=".jpg").endswith("текстурами,.jpg")


def test_folder_name_drops_punctuation_where_it_is_cut():
    title = "Вы сможете получить доступ ко всей сцене, " * 4
    body = post_folder_name(title, PUBLISH_TIME, "id").removeprefix("2024-05-18 — ")
    assert not body.endswith(",")


@pytest.mark.parametrize(
    "lines, expected",
    [
        (["Курс Motion Design", "Урок 1. Введение"], "Урок 1. Введение"),
        (
            ["Урок 1. Введение", "смотрим внимательно"],
            "Урок 1. Введение смотрим внимательно",
        ),
        # Only the last lesson heading starts the name.
        (["Урок 1. Введение", "Урок 2. Практика"], "Урок 2. Практика"),
        ([], ""),
    ],
)
def test_pick_heading(lines, expected):
    assert pick_heading(lines) == expected


def test_pick_heading_without_a_lesson_line_takes_the_last_line():
    assert pick_heading(["раздел", "просто подпись"]) == "просто подпись"


def test_pick_heading_falls_back_to_the_post_title_on_a_paragraph():
    paragraph = "очень длинный абзац " * 10
    assert pick_heading([paragraph], post_title="Название поста") == "Название поста"


def test_media_file_name_matches_the_existing_dump():
    assert (
        media_file_name(
            1, ["Курс Motion Design 1.0", "Урок 1. Введение"], extension=".mp4"
        )
        == "01. Урок 1. Введение.mp4"
    )


def test_media_file_name_numbers_are_zero_padded():
    assert media_file_name(7, ["Урок 7. Свет"], extension=".mp4").startswith("07. ")


def test_media_file_name_falls_back_to_the_attachment_title():
    assert (
        media_file_name(2, [], fallback_title="новая", extension=".zip")
        == "02. новая.zip"
    )


def test_media_file_name_without_any_title_is_still_usable():
    assert media_file_name(3, [], extension=".jpg") == "03.jpg"


def test_unique_file_name_appends_a_counter():
    used: set[str] = set()
    assert unique_file_name("01. Урок.mp4", used) == "01. Урок.mp4"
    assert unique_file_name("01. Урок.mp4", used) == "01. Урок (2).mp4"
    assert unique_file_name("01. Урок.mp4", used) == "01. Урок (3).mp4"


def test_unique_file_name_ignores_case_like_windows_does():
    used: set[str] = set()
    unique_file_name("Photo.JPG", used)
    assert unique_file_name("photo.jpg", used) == "photo (2).jpg"
