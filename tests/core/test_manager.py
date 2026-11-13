"""Tests for Engine and module helpers."""

from pathlib import Path

import pytest
from conftest import Roots

from photo_darkroom_manager.core.engine import _require_one


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
def test_prepare_calls_pass_the_node_folder_and_roots(
    tmp_path: Path, make_engine
) -> None:
    roots = _three_roots(tmp_path)
    mgr = make_engine(roots)
    batch_id = "Camera/2026/2026-09 batch"
    folder = roots.darkroom / batch_id
    folder.mkdir(parents=True)
    (folder / "PUBLISH").mkdir()

    assert mgr.action_prepare_tidy(batch_id).folder == folder
    archive_plan = mgr.action_prepare_archive(batch_id)
    assert archive_plan.source == folder
    assert archive_plan.darkroom_root == roots.darkroom
    assert archive_plan.archive_root == roots.archive
    publish_plan = mgr.action_prepare_publish(batch_id)
    assert publish_plan.batch == folder
    assert publish_plan.showroom_root == roots.showroom
    rename_plan = mgr.action_prepare_rename(batch_id, date="2026-03", title="x")
    assert rename_plan.folder == folder
    assert (rename_plan.date, rename_plan.title) == ("2026-03", "x")
    assert not rename_plan.clear_title
    new_plan = mgr.action_prepare_new_batch("Camera", date="2026-09", title="T")
    assert new_plan.darkroom_root == roots.darkroom
    assert (new_plan.device, new_plan.date, new_plan.title) == (
        "Camera",
        "2026-09",
        "T",
    )
