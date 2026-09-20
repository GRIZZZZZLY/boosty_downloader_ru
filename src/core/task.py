import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import aiofiles
from aiohttp import ClientSession

from core.archive_index import record_post
from core.authorization_provider import AuthorizationProvider
from core.boosty.client import BoostyClient
from core.boosty.defs import (
    BoostyImageDto,
    BoostyAudioDto,
    BoostyFileDto,
    BoostyVideoDto,
    VIDEO_QUALITY_GRADE,
    BoostyPostDto,
)
from core.defs.common import DownloadingSettingsDto
from core.defs.tasks import TaskError
from core.draftjs_converter import DraftJsConverter
from core.logger import setup_logger
from core.naming import (
    POST_TIMEZONE,
    media_file_name,
    post_folder_name,
    sanitize,
    unique_file_name,
)
from core.progress_counter import ProgressCounter
from core.verify import verify_download
from i18n import t
from core.utils import validate_windows_dir_name, sign_url, get_download_settings

logger = setup_logger()


@dataclass
class FinalDownloadTaskDto:
    final_url: str
    save_path: Path
    expected_size: Optional[int] = None


# How many times one file is retried before the task gives up on it.
DOWNLOAD_ATTEMPTS = 3
RETRY_PAUSE_SECONDS = 5


class Task:
    """Репрезентация таска фоновой загрузки файлов"""

    def __init__(
        self,
        semaphore: asyncio.Semaphore,
        author: str,
        post_id: str,
        post_info: Optional[BoostyPostDto] = None,
    ):
        self._semaphore = semaphore
        self.author = author
        self.post_id = post_id
        self.title = None
        self.path = None
        self._percent = 0
        self._downloaded_bytes = 0
        self._done = False
        self._pending = False
        self._error = False
        self._task = None
        self._finished = False
        self._count_files = 0
        self._total_weight = 0
        self._post_info = post_info
        self.error_description: Optional[TaskError] = None
        self._built_client: Optional[BoostyClient] = None

    def ready(self) -> bool:
        return not self._done and not self._pending and not self._error

    @property
    def percent(self) -> float:
        return self._percent / 100

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def pending(self) -> bool:
        return self._pending

    @property
    def total_weight(self) -> int:
        return self._total_weight

    @property
    def count_files(self) -> int:
        return self._count_files

    def launch(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _build_client(self, force: bool = False) -> Optional[BoostyClient]:
        if not self._built_client or force:
            settings = await get_download_settings()
            if not settings:
                logger.error(
                    "Failed get application settings. It may be that the home folder could not be found."
                )
                return None
            auth_token = await AuthorizationProvider.get_authorization_if_valid()
            self._built_client = BoostyClient(
                chunk_size=settings.chunk_size,
                download_timeout=settings.download_timeout,
                auth_token=auth_token,
            )
        return self._built_client

    async def fetch_file_size(self, url: str) -> Optional[int]:
        client = await self._build_client()
        if not client:
            return None
        session = client.get_client_session()
        logger.info(f"Fetching file size for {url}")
        try:
            async with session.head(url) as response:
                logger.debug(f"Got response {response.status}")
                response.raise_for_status()
                return response.content_length
        except Exception as e:
            logger.error("Failed to fetch file size", exc_info=e)
            return None
        finally:
            await session.close()

    async def stop(self):
        if self._task:
            self._task.cancel()
        self._task = None
        self._pending = False
        self._error = True
        self._finished = True
        self.error_description = TaskError.CANCELLED

    async def retry(self):
        if self._done or self._pending:
            return
        self._percent = 0
        self._error = False
        self.error_description = None
        self._finished = False
        self._task = None
        self._total_weight = 0
        self._count_files = 0
        self.launch()

    def _advance_progress(self, amount: int, pbar: ProgressCounter) -> None:
        self._downloaded_bytes += amount
        pbar.update(amount)
        # A retry re-counts bytes it already reported, so the bar is clamped.
        self._percent = min((pbar.n / (pbar.total or 1)) * 100, 100)

    def _already_downloaded(
        self, save_path: Path, expected_size: Optional[int]
    ) -> bool:
        """True when the file on disk is whole and can be left alone.

        A file that is merely present is not enough: an interrupted download
        used to be treated as finished, which is how a truncated archive
        survives unnoticed. The damaged file is left in place until the new
        one has been downloaded and checked, so a failed retry never costs
        what was already there.
        """
        if not save_path.exists():
            return False
        problem = verify_download(save_path, expected_size)
        if problem is None:
            return True
        logger.warning(f"Re-downloading {save_path.name}: {problem}")
        return False

    async def _download_file(
        self,
        session: ClientSession,
        file_url: str,
        save_path: Path,
        pbar: ProgressCounter,
        chunk_size: int = 153600,
        expected_size: Optional[int] = None,
    ):
        if self._already_downloaded(save_path, expected_size):
            logger.info(f"Skip downloading file {save_path} (already complete)")
            await session.close()
            self._advance_progress(save_path.stat().st_size, pbar)
            return

        # The bytes land in a .part file, so an interrupted download is
        # resumable and is never mistaken for a finished one.
        part_path = save_path.with_suffix(save_path.suffix + ".part")
        have = part_path.stat().st_size if part_path.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}

        async with session:
            logger.info(f"Downloading file {file_url} (have {have} bytes)")
            async with session.get(file_url, headers=headers) as response:
                logger.debug(f"Got response {response.status}")
                if response.status == 416:  # nothing left to resume
                    part_path.replace(save_path)
                    self._advance_progress(have, pbar)
                    return
                response.raise_for_status()
                if response.status == 200 and have:
                    logger.info("Server ignored Range, starting over")
                    have = 0
                if have:
                    self._advance_progress(have, pbar)
                mode = "ab" if have else "wb"
                async with aiofiles.open(part_path, mode) as f:
                    logger.debug(f"Writing file {part_path}")
                    async for chunk in response.content.iter_chunked(chunk_size):
                        if not chunk:
                            continue
                        await f.write(chunk)
                        self._advance_progress(len(chunk), pbar)

        problem = verify_download(part_path, expected_size)
        if problem:
            raise ValueError(f"{save_path.name} is damaged: {problem}")
        part_path.replace(save_path)

    def _fallback(self, err: TaskError) -> None:
        self._error = True
        self.error_description = err
        self._finished = True
        self._pending = False

    async def _prepare_download_tasks(
        self,
        post_path: Path,
        post_info: BoostyPostDto,
        settings: DownloadingSettingsDto,
    ) -> List[FinalDownloadTaskDto]:
        download_items = []
        archive = settings.layout == "archive"
        post_title = post_info.title or ""
        # Each attachment type is numbered on its own, so the photos in a post
        # read 01, 02 … regardless of how many videos sit between them.
        counters = {"photo": 0, "video": 0, "audio": 0, "file": 0}
        # The post text is written before the attachments, so its name is
        # already taken.
        used_names: set[str] = {"contents.md", "contents.txt"} if archive else set()

        def archive_name(kind: str, media_item, fallback: str, extension: str) -> str:
            counters[kind] += 1
            return unique_file_name(
                media_file_name(
                    counters[kind],
                    media_item.heading_lines,
                    fallback_title=fallback,
                    post_title=post_title,
                    extension=extension,
                ),
                used_names,
            )

        for media in post_info.media:
            if (
                isinstance(media, BoostyImageDto) and settings.need_download_photos
            ):  # photo
                self._total_weight += media.size
                if archive:
                    file_name = archive_name("photo", media, "", ".jpg")
                else:
                    file_name = media.id + ".jpg"
                download_items.append(
                    FinalDownloadTaskDto(
                        final_url=media.url,
                        save_path=post_path / file_name,
                        expected_size=media.size,
                    )
                )

            elif (
                isinstance(media, BoostyVideoDto) and settings.need_download_videos
            ):  # video
                lborder_quality = VIDEO_QUALITY_GRADE.index(
                    settings.preferred_video_size
                )
                for i in range(lborder_quality, len(VIDEO_QUALITY_GRADE)):
                    url_info = media.player_urls.get(VIDEO_QUALITY_GRADE[i])
                    if url_info:
                        file_size = await self.fetch_file_size(url_info.url)
                        if not file_size:
                            raise ValueError(
                                f"Failed fetch file size for {url_info.url}"
                            )
                        self._total_weight += file_size
                        if archive:
                            file_name = archive_name(
                                "video", media, media.title or "", ".mp4"
                            )
                        else:
                            file_name = validate_windows_dir_name(media.get_title())
                        download_items.append(
                            FinalDownloadTaskDto(
                                final_url=url_info.url,
                                save_path=post_path / file_name,
                                expected_size=file_size,
                            )
                        )
                        break

            elif (
                isinstance(media, BoostyAudioDto) and settings.need_download_audios
            ):  # audio
                if post_info.signed_query:
                    self._total_weight += media.size
                    if archive:
                        counters["audio"] += 1
                        file_name = unique_file_name(
                            sanitize(media.title)
                            or f"audio{counters['audio']:02d}.mp3",
                            used_names,
                        )
                    else:
                        file_name = validate_windows_dir_name(media.get_title())
                    download_items.append(
                        FinalDownloadTaskDto(
                            final_url=sign_url(media.url, post_info.signed_query),
                            save_path=post_path / file_name,
                            expected_size=media.size,
                        )
                    )

            elif (
                isinstance(media, BoostyFileDto) and settings.need_download_files
            ):  # file
                if post_info.signed_query:
                    self._total_weight += media.size
                    if archive:
                        counters["file"] += 1
                        file_name = unique_file_name(
                            sanitize(media.title) or f"file{counters['file']:02d}",
                            used_names,
                        )
                    else:
                        file_name = validate_windows_dir_name(media.title)
                    download_items.append(
                        FinalDownloadTaskDto(
                            final_url=sign_url(media.url, post_info.signed_query),
                            save_path=post_path / file_name,
                            expected_size=media.size,
                        )
                    )

        return download_items

    async def _run(self):
        if self._done or self._pending:
            return None

        self._pending = True
        async with self._semaphore:
            settings = await get_download_settings()
            if not settings:
                logger.error(
                    "Failed get application settings. It may be that the home folder could not be found."
                )
                return self._fallback(TaskError.ERROR)
            client = await self._build_client(force=True)
            if not client:
                logger.error("Failed build client, task skipped")
                return self._fallback(TaskError.ERROR)

            if self._post_info:
                post_info = self._post_info
            else:
                try:
                    post_info = await client.get_post_info(self.author, self.post_id)
                except Exception as e:
                    logger.error(
                        "Failed fetch post info due unexpected error", exc_info=e
                    )
                    return self._fallback(TaskError.ERROR)

            if post_info.title:
                self.title = post_info.title

            if not post_info.has_access:
                logger.error(
                    f"User have no access to the post {self.post_id}, cancelled"
                )
                return self._fallback(TaskError.ACCESS_DENIED)

            downloads_folder = Path(settings.downloads_folder)
            logger.info(f"Home dir: {downloads_folder}")

            try:
                if not os.path.isdir(settings.downloads_folder):
                    logger.error(
                        f"Home directory does not exist: {settings.downloads_folder}, creating..."
                    )
                    downloads_folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error("Failed create or check home directory", exc_info=e)
                return self._fallback(TaskError.NO_HOME_FOLDER)

            author_path = Path(settings.downloads_folder) / self.author
            if settings.layout == "archive":
                post_path = author_path / post_folder_name(
                    post_info.title or "", post_info.publish_time, self.post_id
                )
            else:
                post_path = author_path / self.post_id
                if post_info.title:
                    if title := validate_windows_dir_name(post_info.title):
                        post_path = author_path / (title + "_" + self.post_id)

            self.path = post_path
            if not os.path.isdir(post_path):
                post_path.mkdir(parents=True)
                logger.info(f"Post directory created: {post_path}")

            try:
                parser = DraftJsConverter(post_info.text_content.content)
                post_time = datetime.fromtimestamp(
                    post_info.publish_time, POST_TIMEZONE
                )
                fmt_date = post_time.strftime("%d.%m.%Y %H:%M")
                published = t("Published {date}").format(date=fmt_date)
                if settings.post_text_format == "md":
                    if post_info.title:
                        text_content = f"# {post_info.title}\n"
                    else:
                        text_content = ""
                    text_content += parser.to_markdown() + "\n\n"
                    text_content += f"---\n\n*{published}*\n"
                else:
                    if post_info.title:
                        text_content = f"{post_info.title} \n\n"
                    else:
                        text_content = ""
                    text_content += parser.to_plain_text() + "\n\n"
                    text_content += f"[{published}]\n"
            except Exception as e:
                logger.error(
                    "Failed get post text content due unexpected error", exc_info=e
                )
                text_content = None

            if text_content:
                stem = "contents" if settings.layout == "archive" else "content"
                suffix = ".txt" if settings.post_text_format == "raw" else ".md"
                text_file_path = post_path / (stem + suffix)
                if text_file_path.exists():
                    logger.info(
                        f"Skip creating text file: {text_file_path} (already exists)"
                    )
                else:
                    logger.info(f"Creating text file: {text_file_path}")
                    async with aiofiles.open(
                        text_file_path, "w", encoding="utf-8"
                    ) as f:
                        await f.write(text_content)

            download_items = await self._prepare_download_tasks(
                post_path=post_path, post_info=post_info, settings=settings
            )

            self._count_files = len(download_items)
            with ProgressCounter(total=self._total_weight) as pbar:
                for media in download_items:
                    # A dropped connection retries from where the .part file
                    # stopped, instead of failing the whole post.
                    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
                        session = client.get_client_session()
                        try:
                            await self._download_file(
                                session=session,
                                file_url=media.final_url,
                                save_path=media.save_path,
                                pbar=pbar,
                                chunk_size=settings.chunk_size,
                                expected_size=media.expected_size,
                            )
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger.error(
                                f"Error downloading {media.save_path.name}, "
                                f"attempt {attempt} of {DOWNLOAD_ATTEMPTS}",
                                exc_info=e,
                            )
                            if attempt == DOWNLOAD_ATTEMPTS:
                                return self._fallback(TaskError.ERROR)
                            await asyncio.sleep(RETRY_PAUSE_SECONDS)
                    await asyncio.sleep(0.1)

            # Recorded only once every file is in place, so the index never
            # claims a post that is half downloaded.
            await record_post(author_path, self.post_id, post_path.name)

            self._done = True
            self._percent = 100
            self._pending = False
            self._finished = True

        return None
