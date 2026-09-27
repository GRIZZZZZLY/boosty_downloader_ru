"""Which files a post should have on disk, and which of them are already there.

The download task and the 'What is new' check both need the same answer to
"what should this post's folder contain", so the naming lives here once.

Matching against disk goes by size first and name second. Authors edit old
posts: they insert lessons, which renumbers everything after them, and they
retitle lessons. A file on disk is still the same attachment when its size is
identical to the byte, whatever it is called now.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.boosty.defs import (
    BoostyAudioDto,
    BoostyFileDto,
    BoostyImageDto,
    BoostyPlayerUrlDto,
    BoostyPostDto,
    BoostyVideoDto,
    VIDEO_QUALITY_GRADE,
)
from core.defs.common import DownloadingSettingsDto
from core.naming import media_file_name, sanitize, unique_file_name
from core.utils import sign_url, validate_windows_dir_name

__all__ = [
    "PlannedAttachment",
    "apply_renames",
    "count_new_attachments",
    "pick_video_url",
    "plan_attachments",
    "plan_renames",
    "reconcile_with_disk",
]

# Files the app writes next to the attachments; never an attachment themselves.
SERVICE_NAMES = {"contents.md", "contents.txt", "content.md", "content.txt"}
SERVICE_SUFFIXES = (".part", ".tmp")
# A rename in progress parks the file under this marker for a moment.
RENAMING_MARKER = ".renaming-"


@dataclass
class PlannedAttachment:
    kind: str  # photo, video, audio or file
    file_name: str
    url: str
    # Known up front for everything but video, whose size needs a request.
    expected_size: Optional[int]


def pick_video_url(
    video: BoostyVideoDto, preferred_size: str
) -> Optional[BoostyPlayerUrlDto]:
    """The preferred quality, or the best one below it that exists."""
    start = VIDEO_QUALITY_GRADE.index(preferred_size)
    for quality in VIDEO_QUALITY_GRADE[start:]:
        if url_info := video.player_urls.get(quality):
            return url_info
    return None


def plan_attachments(
    post: BoostyPostDto, settings: DownloadingSettingsDto
) -> List[PlannedAttachment]:
    """Every attachment the settings ask for, with the name it gets on disk."""
    archive = settings.layout == "archive"
    post_title = post.title or ""
    # Each attachment type is numbered on its own, so the photos in a post
    # read 01, 02 … regardless of how many videos sit between them.
    counters = Counter()
    # The post text is written before the attachments, so its name is taken.
    used_names: set[str] = {"contents.md", "contents.txt"} if archive else set()

    def archive_name(kind: str, media, fallback: str, extension: str) -> str:
        counters[kind] += 1
        return unique_file_name(
            media_file_name(
                counters[kind],
                media.heading_lines,
                fallback_title=fallback,
                post_title=post_title,
                extension=extension,
            ),
            used_names,
        )

    planned = []
    for media in post.media:
        if isinstance(media, BoostyImageDto) and settings.need_download_photos:
            name = (
                archive_name("photo", media, "", ".jpg")
                if archive
                else media.id + ".jpg"
            )
            planned.append(PlannedAttachment("photo", name, media.url, media.size))

        elif isinstance(media, BoostyVideoDto) and settings.need_download_videos:
            url_info = pick_video_url(media, settings.preferred_video_size)
            if not url_info:
                continue
            name = (
                archive_name("video", media, media.title or "", ".mp4")
                if archive
                else validate_windows_dir_name(media.get_title())
            )
            planned.append(PlannedAttachment("video", name, url_info.url, None))

        elif isinstance(media, BoostyAudioDto) and settings.need_download_audios:
            if not post.signed_query:
                continue
            if archive:
                counters["audio"] += 1
                name = unique_file_name(
                    sanitize(media.title) or f"audio{counters['audio']:02d}.mp3",
                    used_names,
                )
            else:
                name = validate_windows_dir_name(media.get_title())
            url = sign_url(media.url, post.signed_query)
            planned.append(PlannedAttachment("audio", name, url, media.size))

        elif isinstance(media, BoostyFileDto) and settings.need_download_files:
            if not post.signed_query:
                continue
            if archive:
                counters["file"] += 1
                name = unique_file_name(
                    sanitize(media.title) or f"file{counters['file']:02d}",
                    used_names,
                )
            else:
                name = validate_windows_dir_name(media.title)
            url = sign_url(media.url, post.signed_query)
            planned.append(PlannedAttachment("file", name, url, media.size))

    return planned


def _attachment_files(folder: Path) -> List[Path]:
    """Files in a post folder that are attachments, subfolders included."""
    try:
        return [
            path
            for path in folder.rglob("*")
            if path.is_file()
            and path.name.lower() not in SERVICE_NAMES
            and not path.name.lower().endswith(SERVICE_SUFFIXES)
            and RENAMING_MARKER not in path.name
        ]
    except OSError:
        return []


def count_new_attachments(planned_names: List[str], folder: Path) -> int:
    """How many attachments the post has that its folder does not.

    Counted per file type rather than by name, so a renumbered or retitled
    lesson still counts as present: the author inserting two lessons in the
    middle of a course shows up as two, not as every lesson after them.
    """
    wanted = Counter(Path(name).suffix.lower() for name in planned_names)
    have = Counter(path.suffix.lower() for path in _attachment_files(folder))
    return sum(max(0, count - have[suffix]) for suffix, count in wanted.items())


def reconcile_with_disk(
    wanted: List[Tuple[str, Optional[int]]], folder: Path
) -> Tuple[Dict[int, Path], Dict[int, str]]:
    """Split a post's attachments into those already on disk and those to fetch.

    `wanted` holds (file name, size) per attachment, in post order. Returns the
    attachments found on disk, by index, and the file name each remaining one
    should be downloaded to.

    A file counts as an attachment when its size matches to the byte; the same
    name is only preferred. What is left to download never lands on a file
    that turned out to be another attachment: it gets a free name instead, so
    an update cannot overwrite anything already in the archive.
    """
    files = _attachment_files(folder)
    size_of = {path: path.stat().st_size for path in files}
    present: Dict[int, Path] = {}
    claimed: set[Path] = set()

    # Same name and same size: the file sits where it belongs.
    for index, (name, size) in enumerate(wanted):
        path = folder / name
        if path in size_of and (size is None or size_of[path] == size):
            present[index] = path
            claimed.add(path)

    # Same size under another name: renamed or renumbered since.
    by_size = defaultdict(list)
    for path in files:
        if path not in claimed:
            by_size[size_of[path]].append(path)
    for index, (name, size) in enumerate(wanted):
        if index in present or not size:
            continue
        if pool := by_size.get(size):
            path = pool.pop(0)
            present[index] = path
            claimed.add(path)

    # Everything else is downloaded, never on top of another attachment and
    # never onto a name already given to another download in this run. A
    # same-named file nobody claimed is a damaged copy, and keeps its name so
    # the download repairs it.
    blocked = {path.name.casefold() for path in files}
    assigned: set[str] = set()
    targets: Dict[int, str] = {}
    for index, (name, _size) in enumerate(wanted):
        if index in present:
            continue
        if (folder / name) in claimed or name.casefold() in assigned:
            name = unique_file_name(name, blocked)
        else:
            blocked.add(name.casefold())
        assigned.add(name.casefold())
        targets[index] = name
    return present, targets


def plan_renames(
    planned_names: List[str], present: Dict[int, Path], folder: Path
) -> List[Tuple[Path, Path]]:
    """Renames that bring files on disk in line with the post as it is now.

    Only files already paired with an attachment are renamed, each within the
    folder it sits in, so a course kept in 'Блок N' subfolders keeps them. A
    rename that would land on a file which is no attachment is skipped: that
    file is the person's, and nothing is ever written over it.
    """
    claimed = set(present.values())
    others = {
        str(path).casefold()
        for path in _attachment_files(folder)
        if path not in claimed
    }
    renames = []
    for index, path in sorted(present.items()):
        target = path.with_name(planned_names[index])
        if path.name == target.name or str(target).casefold() in others:
            continue
        renames.append((path, target))
    return renames


def apply_renames(renames: List[Tuple[Path, Path]], log_file: Path) -> None:
    """Rename in two steps, logging first, and roll back if a step fails.

    Two steps because an updated course can swap names between its files: the
    old lesson 13 becomes 16 while a new lesson takes 13. Parking every file
    under a temporary name first means no rename meets a file still in place.
    """
    if not renames:
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        json.dumps(
            {"renamed": [[str(source), str(target)] for source, target in renames]},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    parked: List[Tuple[Path, Path, Path]] = []
    moved: List[Tuple[Path, Path]] = []
    try:
        for number, (source, target) in enumerate(renames):
            temporary = source.with_name(f"{source.name}{RENAMING_MARKER}{number}")
            source.rename(temporary)
            parked.append((source, temporary, target))
        for source, temporary, target in parked:
            if target.exists():
                raise FileExistsError(target)
            temporary.rename(target)
            moved.append((source, target))
    except OSError:
        # Put every file back where it was, then let the caller report it.
        # Newest first: a later move may have taken an earlier file's name.
        done = {source for source, _target in moved}
        for source, target in reversed(moved):
            target.rename(source)
        for source, temporary, _target in parked:
            if source not in done and temporary.exists():
                temporary.rename(source)
        raise
