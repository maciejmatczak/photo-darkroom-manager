"""Tests for the archive merge preview in file_utils."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.file_utils import preview_merge_into_archive


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
