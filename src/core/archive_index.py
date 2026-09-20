"""The record of what has already been downloaded for an author.

Without it, checking for new posts means asking Boosty for every post again
and then skipping files one by one. The index answers "do I have this post"
from disk, so a sync only fetches what is actually missing.

It lives next to the post folders, in the author folder, because it describes
them: `downloads_folder/author/downloaded_index.json`, mapping a post id to
the name of its folder.
"""

import json
from pathlib import Path
from typing import Dict, Iterable, List

import aiofiles

from core.logger import setup_logger

__all__ = [
    "INDEX_FILE_NAME",
    "REMOTE_POSTS_FILE_NAME",
    "author_folder",
    "load_index",
    "missing_post_ids",
    "record_post",
    "save_remote_posts",
]

logger = setup_logger()

INDEX_FILE_NAME = "downloaded_index.json"
REMOTE_POSTS_FILE_NAME = "posts_remote.json"


def author_folder(downloads_folder: str, author: str) -> Path:
    return Path(downloads_folder) / author


async def load_index(folder: Path) -> Dict[str, str]:
    """Post id to folder name. An unreadable index reads as empty."""
    path = folder / INDEX_FILE_NAME
    if not path.exists():
        return {}
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            content = await handle.read()
        loaded = json.loads(content)
    except (OSError, ValueError) as e:
        logger.error(f"Failed to read {path}, treating it as empty", exc_info=e)
        return {}
    if not isinstance(loaded, dict):
        logger.error(f"{path} is not an object, treating it as empty")
        return {}
    return {str(key): str(value) for key, value in loaded.items()}


async def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as handle:
        await handle.write(json.dumps(payload, ensure_ascii=False, indent=1))


async def record_post(folder: Path, post_id: str, folder_name: str) -> None:
    """Add one finished post to the index, keeping the rest of it."""
    index = await load_index(folder)
    if index.get(post_id) == folder_name:
        return
    index[post_id] = folder_name
    try:
        await _write_json(folder / INDEX_FILE_NAME, index)
    except OSError as e:
        logger.error(f"Failed to update the index in {folder}", exc_info=e)


async def save_remote_posts(folder: Path, posts: List[dict]) -> None:
    """Keep the API listing on disk so a comparison works without network."""
    try:
        await _write_json(folder / REMOTE_POSTS_FILE_NAME, posts)
    except OSError as e:
        logger.error(f"Failed to save the post listing in {folder}", exc_info=e)


def missing_post_ids(index: Dict[str, str], remote_ids: Iterable[str]) -> List[str]:
    """The ids present on Boosty but not in the index, order preserved."""
    return [post_id for post_id in remote_ids if post_id not in index]
