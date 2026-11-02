"""Behavioral contracts for device-first intake and mapped destinations."""

from pathlib import Path

import pytest
from conftest import link_dir

from photo_darkroom_manager.core.actions import ActionPlan, Move, NewBatchAction
from photo_darkroom_manager.core.engine import Engine
from photo_darkroom_manager.core.library import validate_device_name


def _apply(action) -> None:
    result = action.execute(_plan(action))
    assert result.success, result


def _plan(action) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


def _new_batch(darkroom: Path, device: str, date: str = "2026-10"):
    return NewBatchAction(darkroom, device, date=date)


@pytest.mark.parametrize("existing", [False, True])
def test_new_batch_existing_and_custom_device(roots, existing: bool) -> None:
    if existing:
        (roots.darkroom / "Camera").mkdir()
    action = _new_batch(roots.darkroom, "Camera")
    result = action.execute(_plan(action))
    batch = roots.darkroom / "Camera/2026/2026-10"
    assert result.success
    assert result.rescan_node_path == batch.parent
    assert (batch / "PUBLISH").is_dir()
    assert not (batch / "PHOTOS").exists()
    assert not (batch / "VIDEOS").exists()


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        ".",
        "..",
        "../Camera",
        "a/b",
        "a\\b",
        "a:b",
        "a\x01b",
        "CON",
        "nul.txt",
        "LPT1",
        "COM9.raw",
        "PUBLISH",
        "photos",
        "Videos",
        "Camera.",
    ],
)
def test_invalid_device_creates_nothing(roots, name: str) -> None:
    out = _new_batch(roots.darkroom, name).prepare()
    assert not isinstance(out, ActionPlan)
    assert out.outcome == "refused"
    assert list(roots.darkroom.iterdir()) == []


@pytest.mark.parametrize("name", ["Camera", "My Camera", "Aparat Łukasza"])
def test_device_names_allow_unicode_and_trim_whitespace(name: str) -> None:
    assert validate_device_name(f"  {name}  ") == name


def test_blocking_device_file_preserved(roots) -> None:
    blocking = roots.darkroom / "Camera"
    blocking.write_bytes(b"keep")
    out = _new_batch(roots.darkroom, "Camera").prepare()
    assert not isinstance(out, ActionPlan)
    assert out.outcome == "refused"
    assert blocking.read_bytes() == b"keep"


def test_device_symlink_outside_darkroom_rejected(roots, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link_dir(roots.darkroom / "Camera", outside)
    out = _new_batch(roots.darkroom, "Camera").prepare()
    assert not isinstance(out, ActionPlan)
    assert out.outcome == "refused"
    assert list(outside.iterdir()) == []


def test_device_symlink_made_after_the_preview_rejected(roots, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    action = _new_batch(roots.darkroom, "Camera")
    plan = _plan(action)
    link_dir(roots.darkroom / "Camera", outside)
    result = action.execute(plan)
    assert result.outcome == "refused"
    assert list(outside.iterdir()) == []


def test_library_devices_includes_empty_directories(roots, engine) -> None:
    mgr = engine
    assert mgr.library_devices() == []
    (roots.darkroom / "Phone").mkdir()
    (roots.darkroom / "Camera").mkdir()
    (roots.darkroom / "notes.txt").write_text("not a device")
    assert mgr.library_devices() == ["Camera", "Phone"]
    (roots.darkroom / "New camera").mkdir()
    assert mgr.library_devices() == ["Camera", "New camera", "Phone"]


def test_scan_device_year_batch_and_scoped_refresh(roots, engine: Engine) -> None:
    mgr = engine
    mgr.library_scan()
    assert mgr.library_node("").children == ()
    result = mgr.action_apply(mgr.action_new_batch("Camera", date="2026-10"))
    assert result.success
    assert result.library_refreshed == ""
    tree = mgr.library_node("")
    device = tree.children[0]
    year = device.children[0]
    batch = year.children[0]
    assert [n.kind for n in (tree, device, year, batch)] == [
        "root",
        "device",
        "year",
        "batch",
    ]
    assert [n.id for n in (device, year, batch)] == [
        "Camera",
        "Camera/2026",
        "Camera/2026/2026-10",
    ]
    (roots.darkroom / batch.id / "loose.jpg").write_bytes(b"image")
    assert mgr.library_refresh(batch.id) == batch.id
    assert all(
        mgr.library_node(n.id).total.image_count == 1
        and "untidy" in mgr.library_node(n.id).issues
        for n in (tree, device, year, batch)
    )
    result = mgr.action_apply(mgr.action_new_batch("Camera", date="2027-01"))
    assert result.library_refreshed == "Camera"
    assert [n.name for n in mgr.library_node("Camera").children] == ["2026", "2027"]


def test_devices_publish_and_archive_independently(roots, engine: Engine) -> None:
    mgr = engine
    for device in ("Camera", "Phone"):
        _apply(mgr.action_new_batch(device, date="2026-10", title="Walk"))
        batch_id = f"{device}/2026/2026-10 Walk"
        batch = roots.darkroom / batch_id
        (batch / "PUBLISH/export.jpg").write_bytes(device.encode())
        (batch / "PHOTOS/nested").mkdir(parents=True)
        (batch / "PHOTOS/nested/original.raw").write_bytes(b"raw")
        publish = mgr.action_publish(batch_id)
        plan = _plan(publish)
        expected = roots.showroom / "2026/2026-10 Walk" / device
        assert expected == mgr.showroom_path(darkroom_path=batch)
        assert {s.target.parent for s in plan.steps if isinstance(s, Move)} == {
            expected
        }
        assert publish.execute(plan).success
        assert (expected / "export.jpg").read_bytes() == device.encode()
        assert not (expected / "PUBLISH").exists()
        nested = batch / "PHOTOS/nested"
        archive = mgr.action_archive(f"{batch_id}/PHOTOS/nested")
        archive_plan = _plan(archive)
        expected_archive = (
            roots.archive / "2026/2026-10 Walk" / device / "PHOTOS/nested"
        )
        assert expected_archive == mgr.archive_path(darkroom_path=nested)
        assert [s.target for s in archive_plan.steps if isinstance(s, Move)] == [
            expected_archive / "original.raw"
        ]
        assert archive.execute(archive_plan).success
        assert (expected_archive / "original.raw").read_bytes() == b"raw"


def test_fully_archived_batch_disappears_from_darkroom_tree(
    roots, engine: Engine
) -> None:
    mgr = engine
    _apply(mgr.action_new_batch("Camera", date="2026-10"))
    batch = roots.darkroom / "Camera/2026/2026-10"
    (batch / "original.raw").write_bytes(b"raw")
    _apply(mgr.action_archive("Camera/2026/2026-10"))
    assert not batch.exists()
    mgr.library_scan()
    assert mgr.library_node("Camera/2026").children == ()


def test_rename_leaves_archive_and_showroom_at_old_name(roots, engine: Engine) -> None:
    mgr = engine
    _apply(mgr.action_new_batch("Camera", date="2026-10"))
    old = roots.darkroom / "Camera/2026/2026-10"
    for root in (roots.archive, roots.showroom):
        (root / "2026/2026-10/Camera").mkdir(parents=True)
    _apply(mgr.action_rename("Camera/2026/2026-10", title="Walk"))
    assert (old.parent / "2026-10 Walk").is_dir()
    for root in (roots.archive, roots.showroom):
        assert (root / "2026/2026-10/Camera").is_dir()
        assert not (root / "2026/2026-10 Walk").exists()


def test_tidy_loose_media_preserves_publish(roots, engine: Engine) -> None:
    mgr = engine
    _apply(mgr.action_new_batch("Camera", date="2026-10"))
    batch = roots.darkroom / "Camera/2026/2026-10"
    for filename in (
        "shot.cr3",
        "shot.jpg",
        "shot.xmp",
        "other.jpg",
        "clip.mp4",
        "PUBLISH/export.jpg",
    ):
        (batch / filename).write_bytes(b"media")
    action = mgr.action_tidy("Camera/2026/2026-10")
    assert mgr.action_execute(action, _plan(action)).success
    assert (batch / "PUBLISH/export.jpg").read_bytes() == b"media"
    for filename in ("shot.cr3", "shot.jpg", "shot.xmp", "other.jpg"):
        assert (batch / "PHOTOS" / filename).is_file()
    assert (batch / "VIDEOS/clip.mp4").is_file()
