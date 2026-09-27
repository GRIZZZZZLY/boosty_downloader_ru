"""The record of what has already been downloaded for an author.

Without it, checking for new posts means asking Boosty for every post again
and then skipping files one by one. The index answers "do I have this post"
from disk, so a sync only fetches what is actually missing.

It lives next to the post folders, in the author's archive folder, because it
describes them: `downloaded_index.json`, mapping a post id to the name of its
folder. The archive folder is `downloads_folder/author` unless one was picked
for that author, so an archive built elsewhere or by other tools still counts.
"""

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import aiofiles
import flet as ft

from core.logger import setup_logger
from core.naming import post_folder_name

__all__ = [
    "INDEX_FILE_NAME",
    "author_folder",
    "downloaded_post_ids",
    "load_index",
    "missing_post_ids",
    "record_post",
    "remember_author_folder",
    "resolve_author_folder",
]

logger = setup_logger()

INDEX_FILE_NAME = "downloaded_index.json"
AUTHOR_FOLDER_KEY = "author-folder:{author}"


def author_folder(downloads_folder: str, author: str) -> Path:
    """The default archive folder of an author."""
    return Path(downloads_folder) / author


async def resolve_author_folder(downloads_folder: str, author: str) -> Path:
    """Where this author's posts live: the folder picked for them, or the default.

    The check for new posts and the download of them both go through here, so
    they can never look in two different places.
    """
    chosen = await ft.SharedPreferences().get(AUTHOR_FOLDER_KEY.format(author=author))
    return Path(chosen) if chosen else author_folder(downloads_folder, author)


async def remember_author_folder(author: str, folder: str) -> None:
    await ft.SharedPreferences().set(AUTHOR_FOLDER_KEY.format(author=author), folder)


async def _read_index(path: Path) -> Optional[Dict[str, str]]:
    """The index, {} when there is none, or None when it exists but is unreadable."""
    if not path.exists():
        return {}
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            loaded = json.loads(await handle.read())
    except (OSError, ValueError) as e:
        logger.error(f"Failed to read {path}", exc_info=e)
        return None
    if not isinstance(loaded, dict):
        logger.error(f"{path} is not an object")
        return None
    return {str(key): str(value) for key, value in loaded.items()}


async def load_index(folder: Path) -> Dict[str, str]:
    """Post id to folder name. An unreadable index reads as empty."""
    return await _read_index(folder / INDEX_FILE_NAME) or {}


async def _write_json(path: Path, payload) -> None:
    """Write through a temporary file, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    async with aiofiles.open(temporary, "w", encoding="utf-8") as handle:
        await handle.write(json.dumps(payload, ensure_ascii=False, indent=1))
    os.replace(temporary, path)


async def record_post(folder: Path, post_id: str, folder_name: str) -> None:
    """Add one finished post to the index, keeping the rest of it.

    If the index is there but cannot be read, nothing is written: rewriting it
    from an empty start would replace every entry with this one post.
    """
    path = folder / INDEX_FILE_NAME
    index = await _read_index(path)
    if index is None:
        logger.error(f"Not updating {path}: it exists but could not be read")
        return
    if index.get(post_id) == folder_name:
        return
    index[post_id] = folder_name
    try:
        await _write_json(path, index)
    except OSError as e:
        logger.error(f"Failed to update the index in {folder}", exc_info=e)


def downloaded_post_ids(index: Dict[str, str], folder: Path, posts: list) -> Set[str]:
    """Posts already on disk: listed in the index, or with their folder present.

    The index is only written by this app. The folder check covers an archive
    built before the index existed or by other tools, in either naming layout:
    `YYYY-MM-DD - Title` for the archive layout, and `Title_id` or a bare `id`
    for the original one.
    """
    have = set(index)
    try:
        names = {entry.name for entry in folder.iterdir() if entry.is_dir()}
    except OSError:
        return have
    trailing_ids = {name.rsplit("_", 1)[-1] for name in names if "_" in name}
    for post in posts:
        if post.id in have:
            continue
        archive_name = post_folder_name(post.title or "", post.publish_time, post.id)
        if archive_name in names or post.id in names or post.id in trailing_ids:
            have.add(post.id)
    return have


def missing_post_ids(have: Iterable[str], remote_ids: Iterable[str]) -> List[str]:
    """The ids present on Boosty but not on disk, order preserved."""
    have = set(have)
    return [post_id for post_id in remote_ids if post_id not in have]
