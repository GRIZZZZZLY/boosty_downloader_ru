"""Choosing which missing posts to download on the 'What is new' screen."""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.downloads_manager import DownloadManager  # noqa: E402
from i18n import set_language  # noqa: E402
from pages.whats_new import WhatsNewPage  # noqa: E402

# 2024-05-18 16:39 Moscow time.
PUBLISH_TIME = 1716039591


@dataclass
class Post:
    id: str
    title: str
    publish_time: int = PUBLISH_TIME
    has_access: bool = True


POSTS = [Post("a", "Курс Motion 3.0"), Post("b", "2 Часть"), Post("c", "")]


def with_page(check):
    """Build the page inside a loop, run the check, cancel background work."""

    async def body():
        before = asyncio.all_tasks()
        try:
            page = WhatsNewPage(DownloadManager())
            page.missing = list(POSTS)
            page._fill_missing(page.missing)
            check(page)
        finally:
            for task in asyncio.all_tasks() - before:
                task.cancel()
            await asyncio.sleep(0)

    set_language("ru")
    asyncio.run(body())


def test_every_missing_post_starts_ticked():
    def check(page):
        assert [post.id for post in page._chosen()] == ["a", "b", "c"]
        assert page.download_label.value == "Скачать выбранное (3)"
        assert not page.download_button.disabled

    with_page(check)


def test_unticked_posts_are_not_downloaded():
    def check(page):
        page.selection["b"].value = False
        assert [post.id for post in page._chosen()] == ["a", "c"]

    with_page(check)


def test_select_none_disables_the_download_button():
    def check(page):
        page._select_all(False, update=False)
        assert page._chosen() == []
        assert page.download_button.disabled
        assert page.download_label.value == "Скачать выбранное (0)"

    with_page(check)


def test_select_all_ticks_everything_back():
    def check(page):
        page._select_all(False, update=False)
        page._select_all(True, update=False)
        assert len(page._chosen()) == 3

    with_page(check)


def test_each_row_shows_the_date_and_falls_back_to_the_id():
    def check(page):
        assert page.selection["a"].label == "18.05.2024  Курс Motion 3.0"
        assert page.selection["c"].label == "18.05.2024  c"

    with_page(check)


def test_select_buttons_are_hidden_for_a_single_post():
    def check(page):
        page._fill_missing(POSTS[:1])
        assert not page.selection_row.visible
        page._fill_missing(POSTS)
        assert page.selection_row.visible

    with_page(check)


def test_an_empty_list_hides_the_controls():
    def check(page):
        page._fill_missing([])
        assert not page.missing_list.visible
        assert not page.download_button.visible

    with_page(check)
