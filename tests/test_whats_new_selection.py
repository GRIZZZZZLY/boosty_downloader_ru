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
        assert not any(button.visible for button in page.select_buttons)
        page._fill_missing(POSTS)
        assert all(button.visible for button in page.select_buttons)

    with_page(check)


def test_the_download_button_shows_even_for_a_single_post():
    """It shares a row with the select buttons, above the list."""

    def check(page):
        page._fill_missing(POSTS[:1])
        assert page.selection_row.visible
        assert page.download_button in page.selection_row.controls

    with_page(check)


def test_an_empty_list_hides_the_controls():
    def check(page):
        page._fill_missing([])
        assert not page.missing_list.visible
        assert not page.selection_row.visible

    with_page(check)


def test_an_updated_post_says_how_many_attachments_are_new():
    def check(page):
        page.new_attachments = {"a": 9}
        page._fill_missing(page.missing)
        assert page.selection["a"].label.endswith("— новых вложений: 9")
        assert "новых" not in page.selection["b"].label

    with_page(check)


def test_an_updated_post_lists_its_new_files_and_the_renames():
    def check(page):
        page.new_attachments = {"a": 2}
        page.update_details = {"a": (["12. Урок 5.mp4", "13. Урок 6.mp4"], 6)}
        page._fill_missing(page.missing)
        row = page.missing_list.controls[0]
        texts = [c.value for c in row.controls[1].content.controls]
        assert texts == [
            "+ 12. Урок 5.mp4",
            "+ 13. Урок 6.mp4",
            "Уже скачанных файлов получат новые номера автора: 6",
        ]
        # A plain new post stays a bare checkbox.
        assert page.missing_list.controls[1] is page.selection["b"]

    with_page(check)
