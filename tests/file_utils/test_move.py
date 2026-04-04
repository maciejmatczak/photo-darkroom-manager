"""Tests for move_dir_safely and indirect cstm_shutil_move coverage."""

from pathlib import Path

import pytest

from photo_darkroom_manager.file_utils import move_dir_safely


def test_move_dir_safely_moves_to_new_target(tmp_path: Path) -> None:
    src = tmp_path / "album"
    src.mkdir()
    (src / "x.txt").write_text("hi", encoding="utf-8")
    dst = tmp_path / "moved_album"

    out, issues = move_dir_safely(src, dst)
    assert out == dst
    assert issues == []
    assert not src.exists()
    assert (dst / "x.txt").read_text(encoding="utf-8") == "hi"


def test_move_dir_safely_source_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        move_dir_safely(tmp_path / "nope", tmp_path / "dest")


def test_move_dir_safely_source_not_directory_raises(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        move_dir_safely(f, tmp_path / "dest")


def test_move_dir_safely_target_exists_raises(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        move_dir_safely(src, dst)
