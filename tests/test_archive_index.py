import asyncio
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.archive_index import (  # noqa: E402
    INDEX_FILE_NAME,
    REMOTE_POSTS_FILE_NAME,
    author_folder,
    load_index,
    missing_post_ids,
    record_post,
    save_remote_posts,
)


def run(coroutine):
    return asyncio.run(coroutine)


def test_index_lives_in_the_author_folder(tmp_path):
    assert author_folder(str(tmp_path), "3dbaza") == tmp_path / "3dbaza"


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


def test_recording_the_same_post_twice_changes_nothing(tmp_path):
    run(record_post(tmp_path, "id-1", "2024-05-18 — Первый"))
    before = (tmp_path / INDEX_FILE_NAME).read_text(encoding="utf-8")
    run(record_post(tmp_path, "id-1", "2024-05-18 — Первый"))
    assert (tmp_path / INDEX_FILE_NAME).read_text(encoding="utf-8") == before


def test_index_survives_a_reread_with_non_ascii_names(tmp_path):
    run(record_post(tmp_path, "id-1", "2024-05-18 — Урок 1. Введение"))
    reread = json.loads((tmp_path / INDEX_FILE_NAME).read_text(encoding="utf-8"))
    assert reread["id-1"] == "2024-05-18 — Урок 1. Введение"


def test_missing_ids_keep_the_order_boosty_returned():
    index = {"b": "folder-b"}
    assert missing_post_ids(index, ["a", "b", "c"]) == ["a", "c"]


def test_nothing_is_missing_when_the_index_covers_everything():
    index = {"a": "f", "b": "f"}
    assert missing_post_ids(index, ["a", "b"]) == []


def test_remote_listing_is_saved_for_an_offline_comparison(tmp_path):
    run(save_remote_posts(tmp_path, [{"id": "a", "title": "Пост"}]))
    saved = json.loads((tmp_path / REMOTE_POSTS_FILE_NAME).read_text(encoding="utf-8"))
    assert saved == [{"id": "a", "title": "Пост"}]
