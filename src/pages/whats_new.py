import asyncio
from datetime import datetime

import flet as ft

import components
from core.archive_index import (
    downloaded_post_ids,
    load_index,
    missing_post_ids,
    remember_author_folder,
    resolve_author_folder,
)
from core.authorization_provider import AuthorizationProvider
from core.boosty.client import BoostyClient
from core.downloads_manager import DownloadManager
from core.logger import setup_logger
from core.naming import POST_TIMEZONE
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
        # One checkbox per missing post, so the person picks what to download.
        self.selection: dict[str, ft.Checkbox] = {}
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
        self.folder_text = ft.Text(
            "", size=13, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True
        )
        self.folder_row = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            visible=False,
            controls=[
                ft.Icon(ft.Icons.FOLDER, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                self.folder_text,
                ft.TextButton(
                    t("Choose another folder"),
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=self.pick_folder,
                ),
            ],
        )
        self.hint_text = ft.Text(
            "", size=13, color=ft.Colors.ORANGE, visible=False, width=640
        )
        self.status_text = ft.Text("", size=16, weight=ft.FontWeight.W_600)
        self.progress = ft.ProgressBar(
            color=ft.Colors.ORANGE, width=500, value=None, visible=False
        )
        self.missing_list = ft.ListView(height=260, spacing=0, visible=False)
        self.selection_row = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            visible=False,
            controls=[
                ft.TextButton(
                    t("Select all"),
                    icon=ft.Icons.CHECK_BOX,
                    on_click=lambda e: self._select_all(True),
                ),
                ft.TextButton(
                    t("Select none"),
                    icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                    on_click=lambda e: self._select_all(False),
                ),
            ],
        )
        self.download_label = ft.Text("", size=17)
        self.download_button = ft.Button(
            content=self.download_label,
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
                            self.folder_row,
                            self.status_text,
                            self.hint_text,
                            self.selection_row,
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
        self._fill_missing([])
        self.hint_text.visible = False
        self.status_text.value = t("Asking Boosty for the list of posts...")

        folder = await resolve_author_folder(settings.downloads_folder, author_name)
        self.folder_text.value = t("Author's archive: {folder}").format(folder=folder)
        self.folder_row.visible = True
        self._set_busy(True)
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

        by_id = {post.id: post for post in remote_posts}
        have = downloaded_post_ids(index, folder, remote_posts)
        missing_ids = missing_post_ids(have, by_id.keys())
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
        # A silent zero looks like a fact; say where the app looked instead.
        if remote_posts and len(missing_ids) == len(remote_posts):
            self.hint_text.value = t(
                "No posts of this author were found in this folder. If the archive "
                "is somewhere else, choose that folder: the check and new downloads "
                "will both use it."
            )
            self.hint_text.visible = True

        self._fill_missing(self.missing)
        self._set_busy(False)

    @staticmethod
    def _post_label(post) -> str:
        """Date first: titles like '2 Часть' are ambiguous without it."""
        date = datetime.fromtimestamp(post.publish_time, POST_TIMEZONE)
        return f"{date:%d.%m.%Y}  {post.title or post.id}"

    def _fill_missing(self, posts) -> None:
        """One checkbox per missing post, all ticked, as before the choice existed."""
        self.selection = {
            post.id: ft.Checkbox(
                label=self._post_label(post),
                value=True,
                on_change=lambda e: self._refresh_download_button(),
            )
            for post in posts
        }
        self.missing_list.controls = list(self.selection.values())
        self.missing_list.visible = bool(posts)
        self.selection_row.visible = len(posts) > 1
        self.download_button.visible = bool(posts)
        self._refresh_download_button(update=False)

    def _chosen(self) -> list:
        """The missing posts whose checkbox is ticked, in the listed order."""
        return [
            post
            for post in self.missing
            if self.selection.get(post.id) and self.selection[post.id].value
        ]

    def _refresh_download_button(self, update: bool = True) -> None:
        count = len(self._chosen())
        self.download_label.value = t("Download selected ({count})").format(count=count)
        self.download_button.disabled = count == 0
        if update:
            self.page.update()

    def _select_all(self, ticked: bool, update: bool = True) -> None:
        for checkbox in self.selection.values():
            checkbox.value = ticked
        self._refresh_download_button(update=update)

    async def pick_folder(self, *_):
        """Point this author at the folder their archive actually lives in."""
        if not self.author_name:
            return
        path = await ft.FilePicker().get_directory_path()
        if not path:
            return
        await remember_author_folder(self.author_name, path)
        await self.check_for_new()

    async def download_missing(self, *_):
        chosen = self._chosen()
        if not chosen:
            return
        self._set_busy(True)
        created = 0
        for post in chosen:
            if await self.manager.add_task(self.author_name, post.id, post):
                created += 1
            self.status_text.value = t("{count} tasks created").format(count=created)
            self.page.update()
            await asyncio.sleep(0.05)

        self.missing = []
        self._fill_missing([])
        self._set_busy(False)
        await self.page.push_route("/downloads-center")
