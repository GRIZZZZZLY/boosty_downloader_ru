import asyncio
import datetime
import os
from pathlib import Path

import aiofiles
import flet as ft

import components
from core.authorization_provider import AuthorizationProvider
from core.browser_login import BrowserLoginError, login_through_browser
from core.downloads_manager import DownloadManager
from core.logger import setup_logger
from i18n import t

logger = setup_logger()


class AuthManagementPage(ft.View):
    def __init__(self, manager: DownloadManager):
        super().__init__()
        self.route = "/auth-management"
        self.copy_script_button = ft.Button(
            t("Copy login script"),
            icon=ft.Icon(ft.Icons.COPY, color=ft.Colors.PRIMARY),
            color=ft.Colors.ON_SURFACE,
            height=50,
            on_click=self.copy_script,
        )
        self.token_text_field = ft.TextField(
            value="",
            hint_text="eyJhdXRob3JpemF0aW9uIjoiYXV0aCIsImV4cGlyZXNfaW4iOiJleHAiLCJmdWxsX2Nvb2tpZSI6ImNvb2sifQ==",
            border=ft.OutlineInputBorder(
                side=ft.BorderSide(color=ft.Colors.TRANSPARENT)
            ),
            filled=True,
            fill_color=ft.Colors.SURFACE_CONTAINER,
            hint_style=ft.TextStyle(color=ft.Colors.GREY_600),
        )
        self.manager = manager
        self.browser_login_button = ft.Button(
            t("Open a browser and log in"),
            icon=ft.Icon(ft.Icons.OPEN_IN_BROWSER, color=ft.Colors.PRIMARY),
            color=ft.Colors.ON_SURFACE,
            height=50,
            width=300,
            on_click=self.login_through_browser,
        )
        self.browser_login_status = ft.Text("", color=ft.Colors.ON_SURFACE_VARIANT)
        self.auth_view = ft.ListView(
            spacing=10,
            padding=20,
            width=650,
            align=ft.Alignment.CENTER,
            auto_scroll=True,
            expand=True,
            controls=[
                ft.Text(
                    t("The simple way: through a browser"),
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    t(
                        "A browser window opens on boosty.to. Log in there as usual, "
                        "and the app picks the login up by itself. The window uses a "
                        "separate profile and closes on its own."
                    )
                ),
                self.browser_login_button,
                self.browser_login_status,
                ft.Divider(),
                ft.Text(
                    t("Or by hand, through the browser console"),
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(t("1. Copy script"), size=20, weight=ft.FontWeight.BOLD),
                ft.Text(t("Click the button to copy script:")),
                self.copy_script_button,
                ft.Text(
                    t("2. Paste script into the browser console on boosty"),
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    t(
                        "Press the F12 key when you are on the boosty page, and then paste the text into the console."
                    )
                ),
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    expand=True,
                    padding=10,
                    border_radius=5,
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO, color=ft.Colors.ON_SURFACE),
                            ft.Text(
                                t(
                                    "Make sure that you are logged in to your account on the website."
                                ),
                                width=570,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ]
                    ),
                ),
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    expand=True,
                    padding=10,
                    border_radius=5,
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO, color=ft.Colors.ON_SURFACE),
                            ft.Text(
                                t(
                                    "If the browser shows a warning about code insertion, follow its instructions. Usually you just need to enter 'allow pasting' and press enter."
                                ),
                                width=570,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ]
                    ),
                ),
                ft.Text(t("3. Authorize app"), size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    t(
                        "Copy the token that appeared in the browser console and paste it here:"
                    )
                ),
                self.token_text_field,
                ft.Button(
                    t("Save token"),
                    icon=ft.Icon(ft.Icons.SAVE, color=ft.Colors.PRIMARY),
                    color=ft.Colors.ON_SURFACE,
                    height=50,
                    width=250,
                    on_click=self.save_new_token,
                ),
            ],
        )
        self.auth_expires_info = ft.Text("", size=20)
        self.deauth_view = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.DONE, color=ft.Colors.PRIMARY, size=30),
                        ft.Text(
                            t("Logged in"),
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PRIMARY,
                        ),
                    ],
                ),
                self.auth_expires_info,
                ft.Button(
                    t("Logout"),
                    width=150,
                    height=50,
                    icon=ft.Icon(ft.Icons.LOGOUT, color=ft.Colors.PRIMARY),
                    color=ft.Colors.ON_SURFACE,
                    on_click=self.logout,
                ),
            ],
        )

    def build(self):
        asyncio.create_task(self.render_page())

    async def render_page(self):
        base_view: "list[ft.Control]" = [
            components.AppBar(self.manager),
            ft.Row(
                [
                    ft.IconButton(
                        ft.Icon(ft.Icons.ARROW_BACK), on_click=self.go_to_index
                    ),
                    ft.Text(
                        t("Authorization management"),
                        size=24,
                        weight=ft.FontWeight.BOLD,
                    ),
                ]
            ),
        ]
        expires_in = await AuthorizationProvider.get_token_valid_to()
        if expires_in:
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                if now < expires_in:
                    delta = expires_in - now
                    days = delta.days
                    hours = delta.seconds // 3600
                    if hours == 0:
                        tail = t("{minutes} minutes.").format(
                            minutes=delta.seconds // 60
                        )
                    else:
                        tail = t("{hours} hours.").format(hours=hours)
                    if days > 0:
                        self.auth_expires_info.value = t(
                            "Token will valid for {days} days, {tail}"
                        ).format(days=days, tail=tail)
                    else:
                        self.auth_expires_info.value = t(
                            "Token will valid for {tail}"
                        ).format(tail=tail)
                    base_view.append(self.deauth_view)
                    self.controls = base_view
                    self.page.update()
                    return
            except Exception as e:
                logger.error(
                    f"Failed decode expires in {expires_in=}, set null", exc_info=e
                )
                await ft.SharedPreferences().remove("ba-expires-in")
        base_view.append(self.auth_view)
        self.controls = base_view
        self.page.update()

    async def go_to_index(self):
        await self.page.push_route("/")

    async def copy_script(self):
        script_path = Path(os.getcwd()) / "js/auth_getter_minify.js"
        async with aiofiles.open(script_path, mode="r") as f:
            await ft.Clipboard().set(await f.read())
            self.copy_script_button.icon = ft.Icon(
                ft.Icons.DONE, color=ft.Colors.PRIMARY
            )
            self.page.update()
            await asyncio.sleep(1)
            self.copy_script_button.icon = ft.Icon(
                ft.Icons.COPY, color=ft.Colors.PRIMARY
            )
            self.page.update()

    async def login_through_browser(self, *_):
        self.browser_login_button.disabled = True
        self.browser_login_status.value = t("Opening a browser...")
        self.page.update()

        def report(_state: str) -> None:
            self.browser_login_status.value = t("Waiting for you to log in...")
            self.page.update()

        try:
            auth_token = await login_through_browser(on_status=report)
        except BrowserLoginError as e:
            logger.error("Browser login failed", exc_info=e)
            self.browser_login_button.disabled = False
            self.browser_login_status.value = ""
            self.page.update()
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(t("Could not log in through a browser")),
                    content=ft.Text(
                        t(
                            "Log in with the console script below, it does not need a "
                            "browser the app can drive."
                        )
                    ),
                    actions=[
                        ft.TextButton(
                            t("Ok"), on_click=lambda e: self.page.pop_dialog()
                        )
                    ],
                    open=True,
                )
            )
            return

        await AuthorizationProvider.authorize(auth_token)
        self.browser_login_button.disabled = False
        self.browser_login_status.value = ""
        self.build()
        self.page.update()

    async def save_new_token(self):
        value = self.token_text_field.value.strip()
        if not value:
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(t("Empty token")),
                    content=ft.Text(t("Type token from console into the text field")),
                    actions=[
                        ft.TextButton(
                            t("Ops, ok"), on_click=lambda e: self.page.pop_dialog()
                        )
                    ],
                    open=True,
                )
            )
            return
        auth_token = AuthorizationProvider.validate_login(value)
        if not auth_token:
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(t("Token is incorrect")),
                    content=ft.Text(t("Are you sure you copied it completely?")),
                    actions=[
                        ft.TextButton(
                            t("I'll check"), on_click=lambda e: self.page.pop_dialog()
                        )
                    ],
                    open=True,
                )
            )
            return
        await AuthorizationProvider.authorize(auth_token)
        self.token_text_field.value = ""
        self.build()
        self.page.update()

    async def logout(self):
        await ft.SharedPreferences().remove("ba-authorization")
        await ft.SharedPreferences().remove("ba-cookie")
        await ft.SharedPreferences().remove("ba-expires-in")
        self.build()
        self.page.update()
