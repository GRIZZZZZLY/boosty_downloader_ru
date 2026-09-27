"""Every screen of the app can be built.

This is what caught the Flet 1.0 breakages: a removed helper or a renamed
class fails here at construction time instead of when someone opens the page.
The pages start background work that needs a live window; that work is
cancelled, only building the control tree is checked.
"""

import asyncio
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from components.task_item import TaskItem  # noqa: E402
from components.theme_picker import ThemePicker  # noqa: E402
from core.downloads_manager import DownloadManager  # noqa: E402
from pages.auth_management import AuthManagementPage  # noqa: E402
from pages.download_image_by_link import DownloadImageByLinkPage  # noqa: E402
from pages.download_post import DownloadPostPage  # noqa: E402
from pages.download_several_posts import DownloadSeveralPostsPage  # noqa: E402
from pages.downloads_center import DownloadsCenterPage  # noqa: E402
from pages.feedback_and_bugs import FeedbackAndBugsPage  # noqa: E402
from pages.merge_author_content import MergeAuthorContentPage  # noqa: E402
from pages.settings_page import SettingsPage  # noqa: E402
from pages.welcome_page import WelcomePage  # noqa: E402
from pages.whats_new import WhatsNewPage  # noqa: E402

PAGES = [
    WelcomePage,
    SettingsPage,
    DownloadPostPage,
    DownloadsCenterPage,
    AuthManagementPage,
    MergeAuthorContentPage,
    DownloadSeveralPostsPage,
    DownloadImageByLinkPage,
    FeedbackAndBugsPage,
    WhatsNewPage,
]


async def _build(factory):
    before = asyncio.all_tasks()
    try:
        factory()
    finally:
        for task in asyncio.all_tasks() - before:
            task.cancel()
        await asyncio.sleep(0)


@pytest.mark.parametrize("page_class", PAGES, ids=lambda cls: cls.__name__)
def test_page_builds(page_class):
    async def build():
        await _build(lambda: page_class(DownloadManager()))

    asyncio.run(build())


@pytest.mark.parametrize("widget_class", [TaskItem, ThemePicker])
def test_component_builds(widget_class):
    asyncio.run(_build(widget_class))
