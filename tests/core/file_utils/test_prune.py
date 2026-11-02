"""Tests for prune helpers in file_utils."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.file_utils import (
    _rmdir_empty_dir,
    prune_empty_dirs,
)

pytestmark = pytest.mark.internal


def test_rmdir_empty_dir_removes_empty_directory(tmp_path: Path) -> None:
    d = tmp_path / "empty"
    d.mkdir()
    _rmdir_empty_dir(d)
    assert not d.exists()


def test_rmdir_empty_dir_non_empty_directory_unchanged(tmp_path: Path) -> None:
    d = tmp_path / "full"
    d.mkdir()
    (d / "f.txt").write_text("x", encoding="utf-8")
    _rmdir_empty_dir(d)
    assert d.is_dir()
    assert (d / "f.txt").exists()


def test_rmdir_empty_dir_missing_path_propagates(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        _rmdir_empty_dir(missing)


def testprune_empty_dirs_removes_nested_empty_tree(tmp_path: Path) -> None:
    top = tmp_path / "src"
    (top / "a" / "b").mkdir(parents=True)
    assert (top / "a" / "b").is_dir()
    prune_empty_dirs(top)
    assert not top.exists()


def testprune_empty_dirs_keeps_nonempty_directories(tmp_path: Path) -> None:
    top = tmp_path / "src"
    leaf = top / "a" / "b"
    leaf.mkdir(parents=True)
    (leaf / "keep.txt").write_text("ok", encoding="utf-8")
    prune_empty_dirs(top)
    assert (leaf / "keep.txt").exists()


def testprune_empty_dirs_two_branches_only_one_has_file(
    tmp_path: Path,
) -> None:
    """One sibling subtree is empty (pruned away); the other keeps a file and stays."""
    top = tmp_path / "src"
    empty_branch = top / "empty_branch"
    nested = empty_branch / "nested"
    nested.mkdir(parents=True)
    files_branch = top / "files_branch"
    files_branch.mkdir()
    (files_branch / "data.txt").write_text("keep", encoding="utf-8")

    prune_empty_dirs(top)

    assert top.is_dir()
    assert not empty_branch.exists()
    assert (files_branch / "data.txt").read_text(encoding="utf-8") == "keep"


def testprune_empty_dirs_not_a_directory_noop(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    prune_empty_dirs(f)
    assert f.is_file()
