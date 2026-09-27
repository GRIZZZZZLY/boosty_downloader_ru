import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.archive_index import (  # noqa: E402
    INDEX_FILE_NAME,
    author_folder,
    downloaded_post_ids,
    load_index,
    missing_post_ids,
    record_post,
)
from core.naming import post_folder_name  # noqa: E402

# 2024-05-18 16:39 Moscow time.
PUBLISH_TIME = 1716039591


@dataclass
class Post:
    id: str
    title: str
    publish_time: int = PUBLISH_TIME


def run(coroutine):
    return asyncio.run(coroutine)


# --- where the archive lives -----------------------------------------------


def test_default_archive_folder_is_named_after_the_author(tmp_path):
    assert author_folder(str(tmp_path), "3dbaza") == tmp_path / "3dbaza"


# --- reading and writing the index -------------------------------------------


def test_missing_index_reads_as_empty(tmp_path):
    assert run(load_index(tmp_path)) == {}


def test_unreadable_index_reads_as_empty_instead_of_crashing(tmp_path):
    (tmp_path / INDEX_FILE_NAME).write_text("{not json", encoding="utf-8")
    assert run(load_index(tmp_path)) == {}


def test_index_that_is_not_an_object_reads_as_empty(tmp_path):
    (tmp_path / INDEX_FILE_NAME).write_text("[1, 2, 3]", encoding="utf-8")
    assert run(load_index(tmp_path)) == {}


def test_recording_a_post_keeps_the_others(tmp_path):
    run(record_post(tmp_path, "id-1", "2024-05-18 — Первый"))
    run(record_post(tmp_path, "id-2", "2024-05-19 — Второй"))
    assert run(load_index(tmp_path)) == {
        "id-1": "2024-05-18 — Первый",
        "id-2": "2024-05-19 — Второй",
    }


def test_an_unreadable_index_is_never_overwritten(tmp_path):
    """Rewriting it from empty would replace every entry with one post."""
    path = tmp_path / INDEX_FILE_NAME
    path.write_text('{"id-1": "folder", BROKEN', encoding="utf-8")
    run(record_post(tmp_path, "id-2", "new folder"))
    assert path.read_text(encoding="utf-8") == '{"id-1": "folder", BROKEN'


def test_writing_leaves_no_temporary_file_behind(tmp_path):
    run(record_post(tmp_path, "id-1", "folder"))
    assert sorted(p.name for p in tmp_path.iterdir()) == [INDEX_FILE_NAME]


def test_recording_the_same_post_twice_changes_nothing(tmp_path):
    run(record_post(tmp_path, "id-1", "2024-05-18 — Первый"))
    before = (tmp_path / INDEX_FILE_NAME).read_text(encoding="utf-8")
    run(record_post(tmp_path, "id-1", "2024-05-18 — Первый"))
    assert (tmp_path / INDEX_FILE_NAME).read_text(encoding="utf-8") == before


def test_index_keeps_the_format_the_archive_tools_write(tmp_path):
    """Same file as the hand-built archive: UTF-8 text, one-space indent."""
    run(record_post(tmp_path, "id-1", "2024-05-18 — Урок 1. Введение"))
    raw = (tmp_path / INDEX_FILE_NAME).read_text(encoding="utf-8")
    assert "Урок 1" in raw
    assert raw == json.dumps(
        {"id-1": "2024-05-18 — Урок 1. Введение"}, ensure_ascii=False, indent=1
    )


# --- is a post already on disk ------------------------------------------------


def test_a_post_in_the_index_counts_as_downloaded(tmp_path):
    posts = [Post("id-1", "Первый")]
    assert downloaded_post_ids({"id-1": "anything"}, tmp_path, posts) == {"id-1"}


def test_a_post_folder_counts_even_without_an_index(tmp_path):
    """The archive built by hand has folders the app would name the same way."""
    post = Post("id-1", "Доступ к композиции")
    (tmp_path / post_folder_name(post.title, post.publish_time, post.id)).mkdir()
    assert downloaded_post_ids({}, tmp_path, [post]) == {"id-1"}


def test_a_folder_in_the_original_layout_counts(tmp_path):
    (tmp_path / "Доступ к композиции_id-1").mkdir()
    (tmp_path / "id-2").mkdir()
    posts = [Post("id-1", "Доступ к композиции"), Post("id-2", "")]
    assert downloaded_post_ids({}, tmp_path, posts) == {"id-1", "id-2"}


def test_a_file_with_the_right_name_is_not_a_post_folder(tmp_path):
    post = Post("id-1", "Первый")
    (tmp_path / post_folder_name(post.title, post.publish_time, post.id)).touch()
    assert downloaded_post_ids({}, tmp_path, [post]) == set()


def test_a_missing_folder_falls_back_to_the_index(tmp_path):
    posts = [Post("id-1", "Первый")]
    gone = tmp_path / "not-there"
    assert downloaded_post_ids({"id-1": "f"}, gone, posts) == {"id-1"}


def test_missing_ids_keep_the_order_boosty_returned():
    assert missing_post_ids({"b"}, ["a", "b", "c"]) == ["a", "c"]


def test_nothing_is_missing_when_everything_is_on_disk():
    assert missing_post_ids({"a", "b"}, ["a", "b"]) == []


# --- which folder holds a post -----------------------------------------------


def test_a_retitled_post_stays_in_its_recorded_folder(tmp_path):
    """The author renames the post; the update must not start a new folder."""
    from core.archive_index import locate_post_folders

    (tmp_path / "2024-05-18 — Старое название").mkdir()
    index = {"id-1": "2024-05-18 — Старое название"}
    found = locate_post_folders(index, tmp_path, [Post("id-1", "Новое название")])
    assert found == {"id-1": tmp_path / "2024-05-18 — Старое название"}


def test_a_post_without_an_index_entry_is_found_by_its_folder_name(tmp_path):
    from core.archive_index import locate_post_folders

    post = Post("id-1", "Доступ к композиции")
    folder = tmp_path / post_folder_name(post.title, post.publish_time, post.id)
    folder.mkdir()
    assert locate_post_folders({}, tmp_path, [post]) == {"id-1": folder}


def test_a_post_with_no_folder_is_not_located(tmp_path):
    from core.archive_index import locate_post_folders

    assert locate_post_folders({}, tmp_path, [Post("id-1", "Нигде")]) == {}
