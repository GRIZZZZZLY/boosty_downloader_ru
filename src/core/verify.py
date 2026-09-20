"""Checks that a downloaded file is whole.

A cut-off download usually still opens: an mp4 plays the first minutes, a zip
lists its entries. The damage only shows up much later, when the archive is
needed. These checks catch it right after the download instead.
"""

import zipfile
from pathlib import Path
from typing import Optional

__all__ = ["has_moov_atom", "is_intact_archive", "mp4_problem", "verify_download"]

ARCHIVE_SUFFIXES = {".zip"}
VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov"}

# An mp4 is a sequence of boxes: 4 bytes of length, then a 4-byte type.
_BOX_HEADER = 8
_LARGE_SIZE = 1


def _walk_boxes(path: Path) -> tuple[bool, bool]:
    """Walk the top-level boxes of an mp4.

    Returns (moov was seen, the boxes end exactly at the end of the file).
    """
    size = path.stat().st_size
    seen_moov = False
    offset = 0
    try:
        with open(path, "rb") as handle:
            while offset + _BOX_HEADER <= size:
                handle.seek(offset)
                header = handle.read(_BOX_HEADER)
                if len(header) < _BOX_HEADER:
                    return seen_moov, False
                box_size = int.from_bytes(header[:4], "big")
                if header[4:8] == b"moov":
                    seen_moov = True
                if box_size == _LARGE_SIZE:  # a 64-bit size follows the header
                    extended = handle.read(8)
                    if len(extended) < 8:
                        return seen_moov, False
                    box_size = int.from_bytes(extended, "big")
                elif box_size == 0:  # this box runs to the end of the file
                    return seen_moov, True
                if box_size < _BOX_HEADER:
                    return seen_moov, False
                offset += box_size
    except OSError:
        return seen_moov, False
    return seen_moov, offset == size


def has_moov_atom(path: Path) -> bool:
    """True when the mp4 carries its index box.

    The `moov` box holds the track index. A video written with `moov` last
    and cut off partway is unplayable, so a missing one is proof of damage.
    """
    return _walk_boxes(path)[0]


def mp4_problem(path: Path) -> Optional[str]:
    """Why the video looks damaged, or None when it looks whole.

    Most videos on Boosty are written for streaming, with `moov` first, so a
    truncated one still has its index. What gives it away is the last box
    claiming more bytes than the file actually holds.
    """
    seen_moov, ends_cleanly = _walk_boxes(path)
    if not seen_moov:
        return "video has no moov atom, the download was cut off"
    if not ends_cleanly:
        return "video ends mid-box, the download was cut off"
    return None


def is_intact_archive(path: Path) -> bool:
    """True when every entry of the archive can be read back."""
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def verify_download(path: Path, expected_size: Optional[int] = None) -> Optional[str]:
    """Return why the file looks damaged, or None when it looks whole."""
    if not path.exists():
        return "file is missing"

    actual_size = path.stat().st_size
    if actual_size == 0:
        return "file is empty"
    if expected_size and actual_size != expected_size:
        return f"size is {actual_size} bytes, expected {expected_size}"

    suffix = path.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return mp4_problem(path)
    if suffix in ARCHIVE_SUFFIXES and not is_intact_archive(path):
        return "archive does not read back"
    return None
