"""Tests for merge/preview helpers in file_utils."""

from pathlib import Path

import pytest

from photo_darkroom_manager.file_utils import (
    merge_tree_into_archive,
    preview_merge_into_archive,
)


def test_preview_merge_no_conflicts_lists_all_leaves(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("a", encoding="utf-8")
    (src / "sub" / "b.txt").write_text("b", encoding="utf-8")
    dest = tmp_path / "dest"

    leaves, dups = preview_merge_into_archive(src, dest)
    assert len(dups) == 0
    assert set(leaves) == {src / "a.txt", src / "sub" / "b.txt"}


def test_preview_merge_detects_blocking_destination(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("1", encoding="utf-8")
    dest = tmp_path / "dest"
    dest.mkdir()
    block = dest / "x.txt"
    block.write_text("exists", encoding="utf-8")

    leaves, dups = preview_merge_into_archive(src, dest)
    assert src / "x.txt" in leaves
    assert dups == ((src / "x.txt", block),)


def test_preview_merge_source_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        preview_merge_into_archive(tmp_path / "missing", tmp_path / "dest")


def test_preview_merge_source_not_directory_raises(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        preview_merge_into_archive(f, tmp_path / "dest")


def test_merge_tree_moves_files_and_prunes_source(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "p" / "q").mkdir(parents=True)
    (src / "p" / "q" / "f.txt").write_text("data", encoding="utf-8")
    dest = tmp_path / "archive"

    result = merge_tree_into_archive(src, dest)
    assert result.duplicates == ()
    assert result.moved_files == 1
    assert not src.exists()
    assert (dest / "p" / "q" / "f.txt").read_text(encoding="utf-8") == "data"


def test_merge_tree_moves_nothing_when_duplicate(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "dup.txt").write_text("from-src", encoding="utf-8")
    dest = tmp_path / "archive"
    dest.mkdir()
    conflict = dest / "dup.txt"
    conflict.write_text("block", encoding="utf-8")

    result = merge_tree_into_archive(src, dest)
    assert result.moved_files == 0
    assert len(result.duplicates) == 1
    assert (src / "dup.txt").exists()
    assert conflict.read_text(encoding="utf-8") == "block"
