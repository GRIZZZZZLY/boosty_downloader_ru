"""Which files a post should have, and how a changed post is matched to disk."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.attachment_plan import (  # noqa: E402
    count_new_attachments,
    plan_attachments,
    reconcile_with_disk,
)
from core.boosty.defs import (  # noqa: E402
    BoostyFileDto,
    BoostyImageDto,
    BoostyPlayerUrlDto,
    BoostyPostDto,
    BoostyVideoDto,
    BoostyVideoSizesType,
)
from core.defs.common import DownloadingSettingsDto  # noqa: E402


def settings(**overrides) -> DownloadingSettingsDto:
    values = dict(
        need_download_photos=True,
        need_download_videos=True,
        need_download_audios=True,
        need_download_files=True,
        chunk_size=153600,
        download_timeout=3600,
        preferred_video_size="ultra_hd",
        post_text_format="md",
        downloads_folder="unused",
        max_parallelism=5,
        layout="archive",
    )
    values.update(overrides)
    return DownloadingSettingsDto(**values)


def video(video_id: str, heading: str, qualities=("full_hd",)) -> BoostyVideoDto:
    return BoostyVideoDto(
        id=video_id,
        title="",
        player_urls={
            BoostyVideoSizesType(q): BoostyPlayerUrlDto(
                url=f"https://cdn/{video_id}/{q}", size=BoostyVideoSizesType(q)
            )
            for q in qualities
        },
        heading_lines=[heading],
    )


def post(*media, signed_query="?sig=1") -> BoostyPostDto:
    return BoostyPostDto(
        has_access=True,
        id="post-1",
        int_id=1,
        publish_time=1716039591,
        title="Курс Motion 3.0",
        signed_query=signed_query,
        media=list(media),
    )


def names(planned):
    return [item.file_name for item in planned]


# --- planning ---------------------------------------------------------------


def test_each_type_is_numbered_on_its_own():
    planned = plan_attachments(
        post(
            video("v1", "Урок 1. Введение"),
            BoostyImageDto(
                id="i1", url="u", width=1, height=1, size=10, heading_lines=["Обложка"]
            ),
            video("v2", "Урок 2. Практика"),
        ),
        settings(),
    )
    assert names(planned) == [
        "01. Урок 1. Введение.mp4",
        "01. Обложка.jpg",
        "02. Урок 2. Практика.mp4",
    ]


def test_a_video_with_no_usable_quality_is_skipped_and_not_numbered():
    planned = plan_attachments(
        post(video("v1", "Урок 1", qualities=()), video("v2", "Урок 2")), settings()
    )
    assert names(planned) == ["01. Урок 2.mp4"]


def test_a_lower_quality_is_used_when_the_preferred_one_is_missing():
    planned = plan_attachments(post(video("v1", "Урок 1", ("high",))), settings())
    assert planned[0].url.endswith("/high")


def test_files_keep_their_own_name_and_need_the_signed_query():
    attachment = BoostyFileDto(id="f", url="https://cdn/f", size=5, title="сцена.zip")
    assert names(plan_attachments(post(attachment), settings())) == ["сцена.zip"]
    assert plan_attachments(post(attachment, signed_query=""), settings()) == []


def test_turned_off_types_are_not_planned():
    planned = plan_attachments(
        post(video("v1", "Урок 1")), settings(need_download_videos=False)
    )
    assert planned == []


def test_the_original_layout_keeps_the_original_names():
    image = BoostyImageDto(id="img-id", url="u", width=1, height=1, size=10)
    planned = plan_attachments(post(image), settings(layout="upstream"))
    assert names(planned) == ["img-id.jpg"]


# --- has the post grown ------------------------------------------------------


def write(folder: Path, name: str, size: int) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_lessons_added_at_the_end_are_counted(tmp_path):
    write(tmp_path, "01. Урок 1.mp4", 10)
    planned = ["01. Урок 1.mp4", "02. Урок 2.mp4", "03. Урок 3.mp4"]
    assert count_new_attachments(planned, tmp_path) == 2


def test_a_renumbered_course_counts_only_what_was_added(tmp_path):
    """Inserting a lesson renames every one after it; that is still one new."""
    for name in ("01. Урок 1.mp4", "02. Урок 2.mp4", "03. Урок 3.mp4"):
        write(tmp_path, name, 10)
    planned = ["01. Урок 1.mp4", "02. Урок 1.5.mp4", "03. Урок 2.mp4", "04. Урок 3.mp4"]
    assert count_new_attachments(planned, tmp_path) == 1


def test_a_removed_lesson_is_not_reported_as_new(tmp_path):
    for name in ("01. a.mp4", "02. b.mp4"):
        write(tmp_path, name, 10)
    assert count_new_attachments(["01. a.mp4"], tmp_path) == 0


def test_service_files_are_not_attachments(tmp_path):
    write(tmp_path, "contents.md", 10)
    write(tmp_path, "01. Урок 1.mp4.part", 10)
    assert count_new_attachments(["01. Урок 1.mp4"], tmp_path) == 1


def test_files_in_block_subfolders_count(tmp_path):
    """Course archives keep lessons in 'Блок N' subfolders."""
    write(tmp_path, "Блок 1/01. Урок 1.mp4", 10)
    assert count_new_attachments(["01. Урок 1.mp4"], tmp_path) == 0


def test_types_are_counted_apart(tmp_path):
    """An extra picture does not hide a missing video."""
    write(tmp_path, "01. Обложка.jpg", 10)
    write(tmp_path, "02. Обложка.jpg", 10)
    assert count_new_attachments(["01. Обложка.jpg", "01. Урок 1.mp4"], tmp_path) == 1


# --- matching a changed post to disk ------------------------------------------


def test_a_file_in_its_place_is_not_downloaded_again(tmp_path):
    write(tmp_path, "01. Урок 1.mp4", 100)
    present, targets = reconcile_with_disk([("01. Урок 1.mp4", 100)], tmp_path)
    assert present == {0: tmp_path / "01. Урок 1.mp4"}
    assert targets == {}


def test_a_retitled_lesson_is_recognised_by_its_size(tmp_path):
    old = write(tmp_path, "12. 5 Урок. Делаем риг и блокинг.mp4", 170676680 % 1000 + 1)
    size = old.stat().st_size
    present, targets = reconcile_with_disk(
        [("15. 8 урок. Блокинг четвертой сцены.mp4", size)], tmp_path
    )
    assert present == {0: old}
    assert targets == {}


def test_only_the_new_lessons_are_downloaded(tmp_path):
    write(tmp_path, "01. Урок 1.mp4", 101)
    write(tmp_path, "02. Урок 2.mp4", 102)
    wanted = [
        ("01. Урок 1.mp4", 101),
        ("02. Урок 1.5.mp4", 150),  # inserted by the author
        ("03. Урок 2.mp4", 102),  # renumbered, same file
    ]
    present, targets = reconcile_with_disk(wanted, tmp_path)
    assert sorted(present) == [0, 2]
    assert targets == {1: "02. Урок 1.5.mp4"}


def test_a_new_lesson_never_overwrites_an_existing_one(tmp_path):
    """The new lesson 02 would take the name of old lesson 02, which moved to 03."""
    kept = write(tmp_path, "02. Урок.mp4", 102)
    wanted = [
        ("02. Урок.mp4", 150),  # a different, new video now carries this name
        ("03. Урок.mp4", 102),  # the old file, renumbered
    ]
    present, targets = reconcile_with_disk(wanted, tmp_path)
    assert present == {1: kept}
    assert targets[0] != "02. Урок.mp4"
    assert kept.read_bytes() == b"x" * 102


def test_a_damaged_file_under_its_own_name_is_repaired_in_place(tmp_path):
    write(tmp_path, "01. Урок 1.mp4", 40)  # cut off, no other attachment is 40 bytes
    present, targets = reconcile_with_disk([("01. Урок 1.mp4", 100)], tmp_path)
    assert present == {}
    assert targets == {0: "01. Урок 1.mp4"}


def test_two_new_files_with_one_free_name_do_not_collide(tmp_path):
    kept = write(tmp_path, "01. Урок.mp4", 5)
    wanted = [("01. Урок.mp4", 7), ("01. Урок (2).mp4", 9), ("02. Старый.mp4", 5)]
    present, targets = reconcile_with_disk(wanted, tmp_path)
    assert present == {2: kept}
    assert len(set(targets.values())) == len(targets)
    assert "01. Урок.mp4" not in targets.values()
