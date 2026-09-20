import struct
import sys
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.verify import (  # noqa: E402
    has_moov_atom,
    is_intact_archive,
    mp4_problem,
    verify_download,
)


def box(box_type: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I", 8 + len(payload)) + box_type + payload


def write_mp4(path: Path, with_moov: bool) -> Path:
    """An mp4 that writes its index last, which is how the damage happens."""
    data = box(b"ftyp", b"isom") + box(b"mdat", b"\x00" * 64)
    if with_moov:
        data += box(b"moov", b"\x00" * 16)
    path.write_bytes(data)
    return path


def test_whole_video_has_its_index(tmp_path):
    assert has_moov_atom(write_mp4(tmp_path / "whole.mp4", with_moov=True))


def test_video_cut_off_before_the_index_is_caught(tmp_path):
    assert not has_moov_atom(write_mp4(tmp_path / "cut.mp4", with_moov=False))


def test_truncated_file_does_not_hang_or_crash(tmp_path):
    path = tmp_path / "half.mp4"
    whole = write_mp4(tmp_path / "whole.mp4", with_moov=True).read_bytes()
    path.write_bytes(whole[: len(whole) // 2])
    assert not has_moov_atom(path)


def test_garbage_is_not_mistaken_for_a_video(tmp_path):
    path = tmp_path / "garbage.mp4"
    path.write_bytes(b"\x00\x00\x00\x00not an mp4 at all")
    assert not has_moov_atom(path)


def write_streaming_mp4(path: Path, payload_bytes: int, actual_bytes: int) -> Path:
    """A streaming mp4: the index comes first, so truncation keeps it.

    `actual_bytes` of media data are written while the mdat header claims
    `payload_bytes`, which is exactly what a cut-off download looks like.
    """
    data = (
        box(b"ftyp", b"isom")
        + box(b"moov", b"\x00" * 32)
        + struct.pack(">I", 8 + payload_bytes)
        + b"mdat"
        + b"\x00" * actual_bytes
    )
    path.write_bytes(data)
    return path


def test_streaming_video_still_has_its_index_when_cut_off(tmp_path):
    """Why the moov check alone is not enough for the videos Boosty serves."""
    path = write_streaming_mp4(
        tmp_path / "cut.mp4", payload_bytes=512, actual_bytes=128
    )
    assert has_moov_atom(path)


def test_cut_off_streaming_video_is_caught_by_the_box_lengths(tmp_path):
    path = write_streaming_mp4(
        tmp_path / "cut.mp4", payload_bytes=512, actual_bytes=128
    )
    problem = mp4_problem(path)
    assert problem is not None and "mid-box" in problem


def test_whole_streaming_video_passes(tmp_path):
    path = write_streaming_mp4(
        tmp_path / "whole.mp4", payload_bytes=512, actual_bytes=512
    )
    assert mp4_problem(path) is None


def test_whole_archive_reads_back(tmp_path):
    path = tmp_path / "whole.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("scene.c4d", "x" * 2048)
    assert is_intact_archive(path)


def test_truncated_archive_is_caught(tmp_path):
    whole = tmp_path / "whole.zip"
    with zipfile.ZipFile(whole, "w") as archive:
        archive.writestr("scene.c4d", "x" * 2048)
    cut = tmp_path / "cut.zip"
    cut.write_bytes(whole.read_bytes()[:-64])
    assert not is_intact_archive(cut)


def test_verify_reports_a_missing_file(tmp_path):
    assert verify_download(tmp_path / "nothing.bin") == "file is missing"


def test_verify_reports_an_empty_file(tmp_path):
    path = tmp_path / "empty.bin"
    path.touch()
    assert verify_download(path) == "file is empty"


def test_verify_reports_a_size_mismatch(tmp_path):
    """This is the check that would have caught the 6.0 MB of a 9.5 MB zip."""
    path = tmp_path / "short.bin"
    path.write_bytes(b"x" * 100)
    problem = verify_download(path, expected_size=200)
    assert problem is not None and "expected 200" in problem


def test_verify_accepts_a_whole_file(tmp_path):
    path = tmp_path / "fine.bin"
    path.write_bytes(b"x" * 100)
    assert verify_download(path, expected_size=100) is None


def test_verify_checks_the_index_of_a_video_of_the_right_size(tmp_path):
    path = write_mp4(tmp_path / "cut.mp4", with_moov=False)
    problem = verify_download(path, expected_size=path.stat().st_size)
    assert problem is not None and "moov" in problem
