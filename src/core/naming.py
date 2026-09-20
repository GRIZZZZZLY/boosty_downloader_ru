"""Naming rules for the archive layout.

The archive layout puts a post in `YYYY-MM-DD — Title` and names each
attachment `NN. Heading`, where the heading comes from the text that the
author wrote right above the attachment. That is what makes a downloaded
course readable without opening every file.

Pure functions only, so they can be tested without the network or Flet.
"""

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.utils import validate_windows_dir_name

__all__ = [
    "POST_TIMEZONE",
    "media_file_name",
    "pick_heading",
    "post_folder_name",
    "sanitize",
    "unique_file_name",
]

# Boosty shows post times in Moscow time, so a folder date matches the site
# whatever the computer's own clock is set to.
POST_TIMEZONE = ZoneInfo("Europe/Moscow")

ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")

# The heading of a lesson, in the forms authors actually write.
LESSON = re.compile(r"^\s*(урок\s*\d+|\d+\s*урок|\d+\s*часть|часть\s*\d+)", re.I)

FOLDER_TITLE_LIMIT = 100
FILE_TITLE_LIMIT = 80
TRAILING_PUNCTUATION = " .,;:-–—!?"


def sanitize(name: str) -> str:
    """Strip what Windows refuses, collapse whitespace, cap the length.

    Whitespace is collapsed first: a text block often holds a heading and its
    description separated by a newline, and removing the newline before
    collapsing would glue the two words together.
    """
    name = WHITESPACE.sub(" ", name)
    name = ILLEGAL_CHARS.sub("", name)
    name = name.strip().rstrip(".")
    return validate_windows_dir_name(name[:150].rstrip())


def _truncate_on_word(text: str, limit: int, strip_punctuation: bool = False) -> str:
    """Cut at the last word boundary before `limit`."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = head.rsplit(" ", 1)[0] if " " in head else head
    return cut.rstrip(TRAILING_PUNCTUATION) if strip_punctuation else cut


def post_folder_name(title: str, publish_time: int, post_id: str) -> str:
    """`YYYY-MM-DD — Title`, or just the date when there is no usable title."""
    date = datetime.fromtimestamp(publish_time, POST_TIMEZONE).strftime("%Y-%m-%d")
    clean = _truncate_on_word(
        sanitize(title or post_id), FOLDER_TITLE_LIMIT, strip_punctuation=True
    )
    return f"{date} — {clean}" if clean else date


def pick_heading(lines: list[str], post_title: str = "") -> str:
    """The name of the attachment, taken from the text blocks above it.

    The text above an attachment usually runs from a section heading down to
    the lesson heading and then a description, so everything from the last
    "Урок N" line onwards is the name. Without such a line the last line is
    the closest thing to a name, unless it is a whole paragraph.
    """
    if not lines:
        return ""
    last_lesson = max(
        (i for i, line in enumerate(lines) if LESSON.match(line)), default=None
    )
    if last_lesson is not None:
        return " ".join(lines[last_lesson:])
    tail = lines[-1]
    if len(tail) <= FOLDER_TITLE_LIMIT:
        return tail
    return post_title or tail[:FOLDER_TITLE_LIMIT]


def media_file_name(
    number: int,
    heading_lines: list[str],
    fallback_title: str = "",
    post_title: str = "",
    extension: str = "",
) -> str:
    """`NN. Heading` plus the extension, numbered per attachment type."""
    base = pick_heading(heading_lines, post_title) or fallback_title or post_title
    base = _truncate_on_word(sanitize(base), FILE_TITLE_LIMIT)
    if not base:
        return f"{number:02d}{extension}"
    return sanitize(f"{number:02d}. {base}") + extension


def unique_file_name(name: str, used: set[str]) -> str:
    """Keep names unique inside one post folder by appending ' (2)', ' (3)'…

    `used` is updated in place, and matching ignores case because Windows
    treats two names differing only in case as the same file.
    """
    if name.casefold() not in used:
        used.add(name.casefold())
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    number = 2
    while f"{stem} ({number}){suffix}".casefold() in used:
        number += 1
    name = f"{stem} ({number}){suffix}"
    used.add(name.casefold())
    return name
