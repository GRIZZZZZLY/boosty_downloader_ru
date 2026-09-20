import asyncio

import flet as ft

import components
from core.archive_index import (
    author_folder,
    load_index,
    missing_post_ids,
    save_remote_posts,
)
from core.authorization_provider import AuthorizationProvider
from core.boosty.client import BoostyClient
from core.downloads_manager import DownloadManager
from core.logger import setup_logger
from core.utils import get_download_settings, parse_author_link
from i18n import t

logger = setup_logger()

PAGE_SIZE = 20
PAUSE_BETWEEN_PAGES = 0.3


class WhatsNewPage(ft.View):
    """Compare an author's posts on Boosty with what is already on disk."""

    def __init__(self, manager: DownloadManager):
        super().__init__()
        self.route = "/whats-new"
        self.manager = manager
        self.missing = []
        self.author_name = ""

        self.text_field = ft.TextField(
            prefix_icon=ft.IconButton(ft.Icons.PERSON, on_click=self.check_for_new),
            hint_text="https://boosty.to/author",
            width=500,
            value="",
            border=ft.OutlineInputBorder(
                side=ft.BorderSide(color=ft.Colors.TRANSPARENT)
            ),
            filled=True,
            fill_color=ft.Colors.SURFACE_CONTAINER,
            hint_style=ft.TextStyle(color=ft.Colors.GREY_600),
        )
        self.status_text = ft.Text("", size=16, weight=ft.FontWeight.W_600)
        self.progress = ft.ProgressBar(
            color=ft.Colors.ORANGE, width=500, value=None, visible=False
        )
        self.missing_list = ft.ListView(height=260, spacing=4, visible=False)
        self.download_button = ft.Button(
            content=ft.Text(t("Download what is missing"), size=17),
            icon=ft.Icon(ft.Icons.DOWNLOAD, color=ft.Colors.PRIMARY, size=16),
            height=50,
            visible=False,
            on_click=self.download_missing,
        )

        self.controls = [
            components.AppBar(manager),
            ft.Row(
                controls=[
                    ft.IconButton(
                        ft.Icon(ft.Icons.ARROW_BACK), on_click=self.go_to_index
                    ),
                    ft.Text(t("What is new"), size=24, weight=ft.FontWeight.BOLD),
                ]
            ),
            ft.Row(
                [
                    ft.Column(
                        [
                            self.progress,
                            ft.Text(
                                t(
                                    "Paste a link to the author's page or the nickname, "
                                    "and the app will compare Boosty with what you already have"
                                )
                            ),
                            self.text_field,
                            ft.Button(
                                content=ft.Text(t("Check"), size=17),
                                icon=ft.Icon(
                                    ft.Icons.SYNC, color=ft.Colors.PRIMARY, size=16
                                ),
                                height=50,
                                width=180,
                                color=ft.Colors.ON_SURFACE,
                                on_click=self.check_for_new,
                            ),
                            self.status_text,
                            self.missing_list,
                            self.download_button,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True,
                        spacing=16,
                    )
                ],
                expand=True,
            ),
        ]

    async def go_to_index(self):
        await self.page.push_route("/")

    def _warn(self, title: str, message: str) -> None:
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(title),
                content=ft.Text(message),
                actions=[
                    ft.TextButton(t("Ok"), on_click=lambda e: self.page.pop_dialog())
                ],
                open=True,
            )
        )

    def _set_busy(self, busy: bool) -> None:
        self.progress.visible = busy
        self.disabled = busy
        self.page.update()

    async def check_for_new(self, *_):
        author_name = parse_author_link((self.text_field.value or "").strip())
        if not author_name:
            self._warn(
                t("Empty author"), t("Type link to author's page or author's nickname")
            )
            return

        settings = await get_download_settings()
        if not settings:
            self._warn(t("Folder does not exist"), t("Download folder does not exist"))
            return

        self.author_name = author_name
        self.missing = []
        self.missing_list.controls = []
        self.missing_list.visible = False
        self.download_button.visible = False
        self.status_text.value = t("Asking Boosty for the list of posts...")
        self._set_busy(True)

        folder = author_folder(settings.downloads_folder, author_name)
        index = await load_index(folder)

        auth_token = await AuthorizationProvider.get_authorization_if_valid()
        client = BoostyClient(
            chunk_size=3600, download_timeout=500, auth_token=auth_token
        )

        remote_posts = []
        offset = None
        try:
            while True:
                post_list = await client.get_posts_list(
                    author_name, limit=PAGE_SIZE, offset=offset
                )
                remote_posts.extend(post_list.data)
                self.status_text.value = t("{count} posts on Boosty").format(
                    count=len(remote_posts)
                )
                self.page.update()
                if post_list.extra.is_last:
                    break
                offset = post_list.extra.offset
                await asyncio.sleep(PAUSE_BETWEEN_PAGES)
        except Exception as e:
            logger.error("Failed to fetch the post list", exc_info=e)
            self._set_busy(False)
            self.status_text.value = ""
            self._warn(
                t("Unexpected error on checking posts"),
                t(
                    "An error has occurred when searching posts. Please, check url "
                    "correctness or try again later."
                ),
            )
            return

        await save_remote_posts(
            folder,
            [
                {
                    "id": post.id,
                    "title": post.title,
                    "publishTime": post.publish_time,
                    "hasAccess": post.has_access,
                }
                for post in remote_posts
            ],
        )

        by_id = {post.id: post for post in remote_posts}
        missing_ids = missing_post_ids(index, by_id.keys())
        self.missing = [
            by_id[post_id] for post_id in missing_ids if by_id[post_id].has_access
        ]
        locked = len(missing_ids) - len(self.missing)

        self.status_text.value = t(
            "{total} posts on Boosty, {have} already downloaded, {missing} missing"
        ).format(
            total=len(remote_posts),
            have=len(remote_posts) - len(missing_ids),
            missing=len(missing_ids),
        )
        if locked:
            self.status_text.value += " " + t("({locked} without access)").format(
                locked=locked
            )

        self.missing_list.controls = [
            ft.Text(f"{post.title or post.id}", size=13) for post in self.missing
        ]
        self.missing_list.visible = bool(self.missing)
        self.download_button.visible = bool(self.missing)
        self._set_busy(False)

    async def download_missing(self, *_):
        if not self.missing:
            return
        self._set_busy(True)
        created = 0
        for post in self.missing:
            if await self.manager.add_task(self.author_name, post.id, post):
                created += 1
            self.status_text.value = t("{count} tasks created").format(count=created)
            self.page.update()
            await asyncio.sleep(0.05)

        self.missing = []
        self.missing_list.visible = False
        self.download_button.visible = False
        self._set_busy(False)
        await self.page.push_route("/downloads-center")
