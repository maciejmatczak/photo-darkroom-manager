"""Tests for archive preview and file-move helpers in file_utils."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.file_utils import (
    move_files,
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


def test_move_files_creates_target_folders(tmp_path: Path) -> None:
    src = tmp_path / "src" / "f.txt"
    src.parent.mkdir()
    src.write_text("data", encoding="utf-8")
    dst = tmp_path / "archive" / "p" / "q" / "f.txt"

    report = move_files([(src, dst)])

    assert report.done == ((src, dst),)
    assert report.failed == ()
    assert dst.read_text(encoding="utf-8") == "data"
    assert not src.exists()


def test_move_files_keeps_going_after_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pairs = []
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
        pairs.append((tmp_path / name, tmp_path / "out" / name))
    real_move = file_utils.cstm_shutil_move

    def flaky(src, dst, *args, **kwargs):
        if src.endswith("b.txt"):
            raise PermissionError("locked")
        return real_move(src, dst, *args, **kwargs)

    monkeypatch.setattr(file_utils, "cstm_shutil_move", flaky)
    report = move_files(pairs)

    assert report.done == (pairs[0], pairs[2])
    assert [(s, d) for s, d, _ in report.failed] == [pairs[1]]
    assert "locked" in report.failed[0][2]
    assert (tmp_path / "b.txt").exists()


def test_move_files_replaces_only_when_asked(tmp_path: Path) -> None:
    src = tmp_path / "new.txt"
    src.write_text("new", encoding="utf-8")
    dst = tmp_path / "out" / "new.txt"
    dst.parent.mkdir()
    dst.write_text("old", encoding="utf-8")

    report = move_files([(src, dst)], replace=True)

    assert report.done == ((src, dst),)
    assert dst.read_text(encoding="utf-8") == "new"
