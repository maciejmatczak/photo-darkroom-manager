"""Behavioral contracts for device-first intake and mapped destinations."""

import os
import subprocess
from pathlib import Path

import pytest

from photo_darkroom_manager.actions import (
    ArchivePlan,
    NewBatchAction,
    PublishPlan,
    TidyPlan,
)
from photo_darkroom_manager.models import validate_device_name


@pytest.mark.parametrize("existing", [False, True])
def test_new_batch_existing_and_custom_device(roots, existing: bool) -> None:
    if existing:
        (roots.darkroom / "Camera").mkdir()
    result = NewBatchAction(roots.darkroom, "Camera", "2026", "10", None, None).execute(
        None
    )
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
    result = NewBatchAction(roots.darkroom, name, "2026", "10", None, None).execute(
        None
    )
    assert not result.success
    assert list(roots.darkroom.iterdir()) == []


@pytest.mark.parametrize("name", ["Camera", "My Camera", "Aparat Łukasza"])
def test_device_names_allow_unicode_and_trim_whitespace(name: str) -> None:
    assert validate_device_name(f"  {name}  ") == name


def test_blocking_device_file_preserved(roots) -> None:
    blocking = roots.darkroom / "Camera"
    blocking.write_bytes(b"keep")
    result = NewBatchAction(roots.darkroom, "Camera", "2026", "10", None, None).execute(
        None
    )
    assert not result.success
    assert blocking.read_bytes() == b"keep"


def test_device_symlink_outside_darkroom_rejected(roots, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (roots.darkroom / "Camera").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            raise pytest.skip.Exception(
                f"Directory symlinks unavailable: {error}"
            ) from error
        # Windows without symlink rights: a junction is an equivalent escape.
        subprocess.run(
            [
                "cmd.exe",
                "/c",
                "mklink",
                "/J",
                str(roots.darkroom / "Camera"),
                str(outside),
            ],
            check=True,
            capture_output=True,
        )
    result = NewBatchAction(roots.darkroom, "Camera", "2026", "10", None, None).execute(
        None
    )
    assert not result.success
    assert list(outside.iterdir()) == []


def test_list_devices_includes_empty_directories(roots, engine) -> None:
    mgr = engine
    assert mgr.list_devices() == []
    (roots.darkroom / "Phone").mkdir()
    (roots.darkroom / "Camera").mkdir()
    (roots.darkroom / "notes.txt").write_text("not a device")
    assert mgr.list_devices() == ["Camera", "Phone"]
    (roots.darkroom / "New camera").mkdir()
    assert mgr.list_devices() == ["Camera", "New camera", "Phone"]


def test_scan_device_year_batch_and_scoped_refresh(roots, engine) -> None:
    mgr = engine
    assert mgr.rescan().children == []
    assert (
        mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None).success
    )
    tree = mgr.rescan()
    device = tree.children[0]
    year = device.children[0]
    batch = year.children[0]
    assert [n.node_type for n in (tree, device, year, batch)] == [
        "root",
        "device",
        "year",
        "batch",
    ]
    assert device.parent is tree and year.parent is device and batch.parent is year
    (batch.path / "loose.jpg").write_bytes(b"image")
    mgr.rescan_subtree(batch)
    assert all(
        n.stats.image_count == 1 and "untidy" in n.issues
        for n in (tree, device, year, batch)
    )
    assert (
        mgr.new_batch_action("Camera", "2027", "01", None, None).execute(None).success
    )
    mgr.rescan_subtree(device)
    assert [n.name for n in device.children] == ["2026", "2027"]


def test_devices_publish_and_archive_independently(roots, engine) -> None:
    mgr = engine
    for device in ("Camera", "Phone"):
        assert (
            mgr.new_batch_action(device, "2026", "10", None, "Walk")
            .execute(None)
            .success
        )
        batch = roots.darkroom / device / "2026/2026-10 Walk"
        (batch / "PUBLISH/export.jpg").write_bytes(device.encode())
        (batch / "PHOTOS/nested").mkdir(parents=True)
        (batch / "PHOTOS/nested/original.raw").write_bytes(b"raw")
        publish = mgr.publish_action(batch)
        plan = publish.prepare()
        assert isinstance(plan, PublishPlan)
        expected = roots.showroom / "2026/2026-10 Walk" / device
        assert plan.target_dir == expected == mgr.showroom_path(darkroom_path=batch)
        assert publish.execute(plan).success
        assert (expected / "export.jpg").read_bytes() == device.encode()
        assert not (expected / "PUBLISH").exists()
        nested = batch / "PHOTOS/nested"
        archive = mgr.archive_action(nested)
        archive_plan = archive.prepare()
        assert isinstance(archive_plan, ArchivePlan)
        expected_archive = (
            roots.archive / "2026/2026-10 Walk" / device / "PHOTOS/nested"
        )
        assert (
            archive_plan.target_dir
            == expected_archive
            == mgr.archive_path(darkroom_path=nested)
        )
        assert archive.execute(archive_plan).success
        assert (expected_archive / "original.raw").read_bytes() == b"raw"


def test_fully_archived_batch_disappears_from_darkroom_tree(roots, engine) -> None:
    mgr = engine
    mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None)
    batch = roots.darkroom / "Camera/2026/2026-10"
    (batch / "original.raw").write_bytes(b"raw")
    action = mgr.archive_action(batch)
    plan = action.prepare()
    assert isinstance(plan, ArchivePlan)
    assert action.execute(plan).success
    assert not batch.exists()
    assert mgr.rescan().children[0].children[0].children == []


def test_rename_leaves_archive_and_showroom_at_old_name(roots, engine) -> None:
    mgr = engine
    mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None)
    old = roots.darkroom / "Camera/2026/2026-10"
    for root in (roots.archive, roots.showroom):
        (root / "2026/2026-10/Camera").mkdir(parents=True)
    assert mgr.rename_action(old, "2026", "10", None, "Walk").execute(None).success
    assert (old.parent / "2026-10 Walk").is_dir()
    for root in (roots.archive, roots.showroom):
        assert (root / "2026/2026-10/Camera").is_dir()
        assert not (root / "2026/2026-10 Walk").exists()


def test_tidy_loose_media_preserves_publish(roots, engine) -> None:
    mgr = engine
    mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None)
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
    action = mgr.tidy_action(batch)
    plan = action.prepare()
    assert isinstance(plan, TidyPlan)
    assert action.execute(plan).success
    assert (batch / "PUBLISH/export.jpg").read_bytes() == b"media"
    for filename in ("shot.cr3", "shot.jpg", "shot.xmp", "other.jpg"):
        assert (batch / "PHOTOS" / filename).is_file()
    assert (batch / "VIDEOS/clip.mp4").is_file()
