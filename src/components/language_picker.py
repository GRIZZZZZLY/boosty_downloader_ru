import asyncio

import flet as ft

from i18n import DEFAULT_LANGUAGE, LANGUAGE_NAMES, get_language, set_language

LANGUAGE_PREFERENCE_KEY = "app-language"

language_flags = {
    "en": ft.Icons.LANGUAGE,
    "ru": ft.Icons.LANGUAGE,
}


async def load_saved_language() -> None:
    """Apply the stored language. Call before the first page is built."""
    stored = await ft.SharedPreferences().get(LANGUAGE_PREFERENCE_KEY)
    set_language(stored or DEFAULT_LANGUAGE)


@ft.control
class LanguagePicker(ft.Dropdown):
    def __init__(self):
        super().__init__()
        self.height = 50
        self.width = 700
        self.border = ft.OutlineInputBorder(
            side=ft.BorderSide(color=ft.Colors.TRANSPARENT)
        )
        self.filled = True
        self.fill_color = ft.Colors.SURFACE_CONTAINER
        self.text_size = 14
        self.content_padding = ft.Padding.symmetric(horizontal=16, vertical=12)
        self.prefix_icon = ft.Icons.LANGUAGE
        self.value = get_language()
        self.on_select = lambda e: asyncio.create_task(self.apply_language(e.data))
        self.options = [
            ft.dropdown.Option(key=code, text=name)
            for code, name in LANGUAGE_NAMES.items()
        ]

    async def apply_language(self, language: str):
        if language == get_language():
            return
        await ft.SharedPreferences().set(LANGUAGE_PREFERENCE_KEY, language)
        set_language(language)
        self.value = language
        # Every label is translated while a page is built, so the whole view
        # tree has to be built again for the new language to show up.
        self.page.on_route_change(None)
