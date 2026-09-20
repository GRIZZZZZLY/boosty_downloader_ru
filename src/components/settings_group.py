import asyncio

import flet as ft

import __version__ as app_version
import components
from core.utils import get_download_settings
from i18n import t


@ft.control
class SettingsGroup(ft.ListView):
    def __init__(self):
        super().__init__()
        self.align = ft.Alignment.CENTER
        self.expand = True
        self.spacing = 10
        self.padding = 5
        self.width = 700
        self.disabled = True

        self.current_download_folder_text = ft.Text(
            value=t("Fetching..."), size=20, color=ft.Colors.ON_SURFACE_VARIANT
        )
        self.switch_download_photos = ft.Switch(
            label=t("Download photos"), value=True, padding=10
        )
        self.switch_download_videos = ft.Switch(
            label=t("Download videos"), value=True, padding=10
        )
        self.switch_download_audios = ft.Switch(
            label=t("Download audios"), value=True, padding=10
        )
        self.switch_download_files = ft.Switch(
            label=t("Download attached files"), value=True, padding=10
        )
        self.video_size_dropdown = ft.Dropdown(
            width=700,
            value="ultra_hd",
            label=t("Restrict video size"),
            border_color=ft.Colors.TRANSPARENT,
            filled=True,
            fill_color=ft.Colors.SURFACE_CONTAINER,
            options=[
                ft.DropdownOption(key="low", text=t("Low")),
                ft.DropdownOption(key="medium", text=t("Medium")),
                ft.DropdownOption(key="high", text=t("High")),
                ft.DropdownOption(key="full_hd", text=t("Full HD")),
                ft.DropdownOption(key="ultra_hd", text=t("Ultra HD (no restrict)")),
            ],
        )
        self.post_text_format_dropdown = ft.Dropdown(
            width=700,
            value="md",
            label=t("Post text format"),
            border_color=ft.Colors.TRANSPARENT,
            filled=True,
            fill_color=ft.Colors.SURFACE_CONTAINER,
            options=[
                ft.DropdownOption(key="md", text=t("Markdown file (.md)")),
                ft.DropdownOption(key="raw", text=t("Text file (.txt)")),
            ],
        )
        self.layout_dropdown = ft.Dropdown(
            width=700,
            value="archive",
            label=t("Folder and file names"),
            border_color=ft.Colors.TRANSPARENT,
            filled=True,
            fill_color=ft.Colors.SURFACE_CONTAINER,
            options=[
                ft.DropdownOption(
                    key="archive", text=t("Archive: date in folder, numbered files")
                ),
                ft.DropdownOption(key="upstream", text=t("Original: post id in names")),
            ],
        )
        self.chunk_size_textfield = ft.TextField(
            label=t("Chunk size"),
            border=ft.UnderlineInputBorder(),
            input_filter=ft.NumbersOnlyInputFilter(),
            value="0",
        )
        self.download_timeout_textfield = ft.TextField(
            label=t("Download timeout (sec.)"),
            border=ft.UnderlineInputBorder(),
            input_filter=ft.NumbersOnlyInputFilter(),
            value="0",
        )
        self.max_parallelism_textfield = ft.TextField(
            label=t("Maximum download parallelism"),
            border=ft.UnderlineInputBorder(),
            input_filter=ft.NumbersOnlyInputFilter(),
            value="0",
        )
        self.controls = [
            ft.Text(
                spans=[
                    ft.TextSpan(
                        f"{app_version.NAME} {app_version.VERSION} ",
                        ft.TextStyle(
                            weight=ft.FontWeight.BOLD,
                            size=25,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        url=app_version.URL,
                    ),
                    ft.TextSpan(f"build v{app_version.BUILD}"),
                ]
            ),
            ft.Text(t("Download folder"), theme_style=ft.TextThemeStyle.LABEL_MEDIUM),
            ft.Button(
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                content=ft.Container(
                    height=50,
                    padding=ft.Padding.all(5),
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(
                                ft.Icons.FOLDER,
                                size=20,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            self.current_download_folder_text,
                        ],
                    ),
                ),
                on_click=lambda e: asyncio.create_task(self.pick_download_folder()),
            ),
            ft.Text(t("App theme"), theme_style=ft.TextThemeStyle.LABEL_MEDIUM),
            components.ThemePicker(),
            ft.Text(t("App language"), theme_style=ft.TextThemeStyle.LABEL_MEDIUM),
            components.LanguagePicker(),
            ft.Text(t("Content settings"), theme_style=ft.TextThemeStyle.LABEL_MEDIUM),
            self.switch_download_photos,
            self.switch_download_videos,
            self.switch_download_audios,
            self.switch_download_files,
            ft.Column(
                spacing=25,
                controls=[
                    self.video_size_dropdown,
                    self.post_text_format_dropdown,
                    self.layout_dropdown,
                ],
            ),
            ft.Text(t("Download settings"), theme_style=ft.TextThemeStyle.LABEL_MEDIUM),
            self.chunk_size_textfield,
            self.download_timeout_textfield,
            self.max_parallelism_textfield,
            ft.FilledButton(
                t("Save"),
                height=50,
                margin=15,
                on_click=lambda e: asyncio.create_task(self.apply_settings()),
            ),
        ]

        asyncio.create_task(self.set_initial_values())

    async def pick_download_folder(self):
        path = await ft.FilePicker().get_directory_path()
        if path:
            await ft.SharedPreferences().set("download-folder", path)
            self.current_download_folder_text.value = path
            self.page.update()

    async def apply_settings(self):
        new_chunk_size = self.chunk_size_textfield.value
        if not new_chunk_size or not 10000 <= int(new_chunk_size) <= 500000:
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(t("Chunk size")),
                    content=ft.Text(t("Please enter value between 10000 and 500000.")),
                    actions=[
                        ft.TextButton(
                            t("Understand"), on_click=lambda e: self.page.pop_dialog()
                        )
                    ],
                    open=True,
                )
            )
            return

        new_download_timeout = self.download_timeout_textfield.value
        if not new_download_timeout or int(new_download_timeout) < 10:
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(t("Download timeout (sec.)")),
                    content=ft.Text(
                        t("Not recommended to set timeout less, than 10 seconds.")
                    ),
                    actions=[
                        ft.TextButton(
                            t("Understand"), on_click=lambda e: self.page.pop_dialog()
                        )
                    ],
                    open=True,
                )
            )
            return

        new_max_parallelism = self.max_parallelism_textfield.value
        if not new_max_parallelism or not 1 <= int(new_max_parallelism) <= 10:
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(t("Maximum download parallelism")),
                    content=ft.Text(t("Please enter value between 1 and 10.")),
                    actions=[
                        ft.TextButton(
                            t("Understand"), on_click=lambda e: self.page.pop_dialog()
                        )
                    ],
                    open=True,
                )
            )
            return

        await ft.SharedPreferences().set(
            "need-download-photos", str(self.switch_download_photos.value)
        )
        await ft.SharedPreferences().set(
            "need-download-videos", str(self.switch_download_videos.value)
        )
        await ft.SharedPreferences().set(
            "need-download-audios", str(self.switch_download_audios.value)
        )
        await ft.SharedPreferences().set(
            "need-download-files", str(self.switch_download_files.value)
        )

        await ft.SharedPreferences().set("download-chunk-size", str(new_chunk_size))
        await ft.SharedPreferences().set("download-timeout", str(new_download_timeout))
        await ft.SharedPreferences().set(
            "download-max-parallelism", str(new_max_parallelism)
        )
        await ft.SharedPreferences().set(
            "post-text-format", str(self.post_text_format_dropdown.value)
        )
        await ft.SharedPreferences().set(
            "preferred-video-size", str(self.video_size_dropdown.value)
        )
        await ft.SharedPreferences().set(
            "content-layout", str(self.layout_dropdown.value)
        )

        self.page.show_dialog(ft.SnackBar(ft.Text(t("Saved"))))

    async def set_initial_values(self):
        settings = await get_download_settings()

        self.switch_download_photos.value = settings.need_download_photos
        self.switch_download_videos.value = settings.need_download_videos
        self.switch_download_audios.value = settings.need_download_audios
        self.switch_download_files.value = settings.need_download_files
        self.chunk_size_textfield.value = str(settings.chunk_size)
        self.download_timeout_textfield.value = str(settings.download_timeout)
        self.max_parallelism_textfield.value = str(settings.max_parallelism)
        self.current_download_folder_text.value = settings.downloads_folder
        self.video_size_dropdown.value = settings.preferred_video_size
        self.post_text_format_dropdown.value = settings.post_text_format
        self.layout_dropdown.value = settings.layout
        self.disabled = False
        self.page.update()
