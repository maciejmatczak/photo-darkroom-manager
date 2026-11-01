"""Tests for Engine and module helpers."""

from pathlib import Path

import pytest
from conftest import Roots

from photo_darkroom_manager.actions import (
    ArchiveAction,
    NewBatchAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.engine import _require_one


def _three_roots(tmp_path: Path) -> Roots:
    root = tmp_path / "workspace"
    darkroom = root / "darkroom"
    showroom = root / "showroom"
    archive = root / "archive"
    darkroom.mkdir(parents=True)
    showroom.mkdir()
    archive.mkdir()
    return Roots(darkroom.resolve(), showroom.resolve(), archive.resolve())


@pytest.mark.internal
def test_require_one_accepts_single_path() -> None:
    _require_one(Path("/a"), None)
    _require_one(None, Path("/b"))


@pytest.mark.internal
def test_require_one_rejects_zero_or_two() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        _require_one(None, None)
    with pytest.raises(ValueError, match="exactly one"):
        _require_one(Path("/a"), Path("/b"))


@pytest.mark.parametrize("tail", [Path(), Path("PHOTOS/nested")])
def test_manager_maps_between_all_roots(
    tmp_path: Path, tail: Path, make_engine
) -> None:
    roots = _three_roots(tmp_path)
    mgr = make_engine(roots)
    working = roots.darkroom / "Camera/2026/2026-10 Walk" / tail
    archived = roots.archive / "2026/2026-10 Walk/Camera" / tail
    published = roots.showroom / "2026/2026-10 Walk/Camera" / tail
    assert mgr.darkroom_path(archive_path=archived) == working
    assert mgr.darkroom_path(showroom_path=published) == working
    assert mgr.archive_path(darkroom_path=working) == archived
    assert mgr.archive_path(showroom_path=published) == archived
    assert mgr.showroom_path(darkroom_path=working) == published
    assert mgr.showroom_path(archive_path=archived) == published


@pytest.mark.internal
def test_path_helpers_reject_zero_or_two_kwargs(tmp_path: Path, make_engine) -> None:
    roots = _three_roots(tmp_path)
    mgr = make_engine(roots)
    p = roots.darkroom / "2026" / "a"
    with pytest.raises(ValueError, match="exactly one"):
        mgr.darkroom_path()
    with pytest.raises(ValueError, match="exactly one"):
        mgr.darkroom_path(
            archive_path=roots.archive / "x",
            showroom_path=roots.showroom / "x",
        )
    with pytest.raises(ValueError, match="exactly one"):
        mgr.showroom_path()
    with pytest.raises(ValueError, match="exactly one"):
        mgr.showroom_path(darkroom_path=p, archive_path=p)
    with pytest.raises(ValueError, match="exactly one"):
        mgr.archive_path()
    with pytest.raises(ValueError, match="exactly one"):
        mgr.archive_path(darkroom_path=p, showroom_path=p)


@pytest.mark.internal
def test_factory_methods_return_actions_with_expected_paths(
    tmp_path: Path, make_engine
) -> None:
    roots = _three_roots(tmp_path)
    mgr = make_engine(roots)
    folder = roots.darkroom / "Camera" / "2026" / "2026-09 batch"
    batch = folder

    t = mgr.action_tidy(folder)
    assert isinstance(t, TidyAction)
    assert t._folder_path == folder

    ar = mgr.action_archive(folder)
    assert isinstance(ar, ArchiveAction)
    assert ar._folder_path == folder
    assert ar._darkroom_path == roots.darkroom
    assert ar._archive_path == roots.archive

    pub = mgr.action_publish(batch)
    assert isinstance(pub, PublishAction)
    assert pub._batch_path == batch
    assert pub._showroom_path == roots.showroom
    assert pub._darkroom_path == roots.darkroom

    ren = mgr.action_rename(batch, "2026", "03", None, "new name")
    assert isinstance(ren, RenameAction)
    assert ren._batch_path == batch
    assert ren._year == "2026"
    assert ren._month == "03"
    assert ren._day is None
    assert ren._name == "new name"
    assert ren._darkroom_path == roots.darkroom

    na = mgr.action_new_batch("Camera", "2026", "09", None, "Title")
    assert isinstance(na, NewBatchAction)
    assert na._darkroom_path == roots.darkroom
    assert na._year == "2026"
    assert na._month == "09"
    assert na._day is None
    assert na._name == "Title"
