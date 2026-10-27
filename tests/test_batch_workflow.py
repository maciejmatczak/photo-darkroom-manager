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
from photo_darkroom_manager.manager import DarkroomManager
from photo_darkroom_manager.models import validate_device_name


@pytest.mark.parametrize("existing", [False, True])
def test_new_batch_existing_and_custom_device(settings, existing: bool) -> None:
    if existing:
        (settings.darkroom / "Camera").mkdir()
    result = NewBatchAction(
        settings.darkroom, "Camera", "2026", "10", None, None
    ).execute(None)
    batch = settings.darkroom / "Camera/2026/2026-10"
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
def test_invalid_device_creates_nothing(settings, name: str) -> None:
    result = NewBatchAction(settings.darkroom, name, "2026", "10", None, None).execute(
        None
    )
    assert not result.success
    assert list(settings.darkroom.iterdir()) == []


@pytest.mark.parametrize("name", ["Camera", "My Camera", "Aparat Łukasza"])
def test_device_names_allow_unicode_and_trim_whitespace(name: str) -> None:
    assert validate_device_name(f"  {name}  ") == name


def test_blocking_device_file_preserved(settings) -> None:
    blocking = settings.darkroom / "Camera"
    blocking.write_bytes(b"keep")
    result = NewBatchAction(
        settings.darkroom, "Camera", "2026", "10", None, None
    ).execute(None)
    assert not result.success
    assert blocking.read_bytes() == b"keep"


def test_device_symlink_outside_darkroom_rejected(settings, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (settings.darkroom / "Camera").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(reason=f"Directory symlinks unavailable: {error}")
        subprocess.run(
            [
                "cmd.exe",
                "/c",
                "mklink",
                "/J",
                str(settings.darkroom / "Camera"),
                str(outside),
            ],
            check=True,
            capture_output=True,
        )
    result = NewBatchAction(
        settings.darkroom, "Camera", "2026", "10", None, None
    ).execute(None)
    assert not result.success
    assert list(outside.iterdir()) == []


def test_list_devices_includes_empty_directories(settings) -> None:
    mgr = DarkroomManager(settings)
    assert mgr.list_devices() == []
    (settings.darkroom / "Phone").mkdir()
    (settings.darkroom / "Camera").mkdir()
    (settings.darkroom / "notes.txt").write_text("not a device")
    assert mgr.list_devices() == ["Camera", "Phone"]
    (settings.darkroom / "New camera").mkdir()
    assert mgr.list_devices() == ["Camera", "New camera", "Phone"]


def test_scan_device_year_batch_and_scoped_refresh(settings) -> None:
    mgr = DarkroomManager(settings)
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


def test_devices_publish_and_archive_independently(settings) -> None:
    mgr = DarkroomManager(settings)
    for device in ("Camera", "Phone"):
        assert (
            mgr.new_batch_action(device, "2026", "10", None, "Walk")
            .execute(None)
            .success
        )
        batch = settings.darkroom / device / "2026/2026-10 Walk"
        (batch / "PUBLISH/export.jpg").write_bytes(device.encode())
        (batch / "PHOTOS/nested").mkdir(parents=True)
        (batch / "PHOTOS/nested/original.raw").write_bytes(b"raw")
        publish = mgr.publish_action(batch)
        plan = publish.prepare()
        assert isinstance(plan, PublishPlan)
        expected = settings.showroom / "2026/2026-10 Walk" / device
        assert plan.target_dir == expected == mgr.showroom_path(darkroom_path=batch)
        assert publish.execute(plan).success
        assert (expected / "export.jpg").read_bytes() == device.encode()
        assert not (expected / "PUBLISH").exists()
        nested = batch / "PHOTOS/nested"
        archive = mgr.archive_action(nested)
        archive_plan = archive.prepare()
        assert isinstance(archive_plan, ArchivePlan)
        expected_archive = (
            settings.archive / "2026/2026-10 Walk" / device / "PHOTOS/nested"
        )
        assert (
            archive_plan.target_dir
            == expected_archive
            == mgr.archive_path(darkroom_path=nested)
        )
        assert archive.execute(archive_plan).success
        assert (expected_archive / "original.raw").read_bytes() == b"raw"


def test_fully_archived_batch_disappears_from_darkroom_tree(settings) -> None:
    mgr = DarkroomManager(settings)
    mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None)
    batch = settings.darkroom / "Camera/2026/2026-10"
    (batch / "original.raw").write_bytes(b"raw")
    action = mgr.archive_action(batch)
    plan = action.prepare()
    assert isinstance(plan, ArchivePlan)
    assert action.execute(plan).success
    assert not batch.exists()
    assert mgr.rescan().children[0].children[0].children == []


def test_rename_leaves_archive_and_showroom_at_old_name(settings) -> None:
    mgr = DarkroomManager(settings)
    mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None)
    old = settings.darkroom / "Camera/2026/2026-10"
    for root in (settings.archive, settings.showroom):
        (root / "2026/2026-10/Camera").mkdir(parents=True)
    assert mgr.rename_action(old, "2026", "10", None, "Walk").execute(None).success
    assert (old.parent / "2026-10 Walk").is_dir()
    for root in (settings.archive, settings.showroom):
        assert (root / "2026/2026-10/Camera").is_dir()
        assert not (root / "2026/2026-10 Walk").exists()


def test_tidy_loose_media_preserves_publish(settings) -> None:
    mgr = DarkroomManager(settings)
    mgr.new_batch_action("Camera", "2026", "10", None, None).execute(None)
    batch = settings.darkroom / "Camera/2026/2026-10"
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
