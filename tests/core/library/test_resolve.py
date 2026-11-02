"""Tests for resolving darkroom paths and typed ids to on-disk ids."""

from pathlib import Path

import pytest
from conftest import link_dir

from photo_darkroom_manager.core.library import (
    PathOutsideDarkroomError,
    canonical_id,
    resolve_path,
)
from photo_darkroom_manager.core.library._resolve import on_disk_name

BATCH = "Camera/2026/2026-10 Walk"


@pytest.fixture
def darkroom(tmp_path: Path) -> Path:
    root = tmp_path / "darkroom"
    (root / BATCH / "PUBLISH").mkdir(parents=True)
    return root


# ---------------------------------------------------------------------------
# engine/library-index: resolving a darkroom path, ids follow on-disk names
# ---------------------------------------------------------------------------


def test_batch_path(darkroom: Path) -> None:
    assert resolve_path(darkroom, darkroom / BATCH) == BATCH


def test_archive_path(darkroom: Path, tmp_path: Path) -> None:
    archived = tmp_path / "archive" / "2026"
    with pytest.raises(PathOutsideDarkroomError) as exc:
        resolve_path(darkroom, archived)
    assert exc.value.path == archived
    assert exc.value.root == darkroom


def test_lower_case_path_on_a_case_insensitive_disk(darkroom: Path) -> None:
    assert resolve_path(darkroom, darkroom / BATCH.lower()) == BATCH


def test_publish_folder_typed_in_lower_case(darkroom: Path) -> None:
    assert canonical_id(darkroom, f"{BATCH}/publish") == f"{BATCH}/PUBLISH"


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


@pytest.mark.internal
def test_root_and_dot_dot_paths(darkroom: Path) -> None:
    assert resolve_path(darkroom, darkroom) == ""
    assert resolve_path(darkroom, darkroom / BATCH / ".." / "..") == "Camera"
    with pytest.raises(PathOutsideDarkroomError):
        resolve_path(darkroom, darkroom / "..")


@pytest.mark.internal
def test_sibling_with_the_root_as_name_prefix_is_outside(darkroom: Path) -> None:
    with pytest.raises(PathOutsideDarkroomError):
        resolve_path(darkroom, darkroom.with_name("darkroom-old") / "Camera")


@pytest.mark.internal
def test_missing_folders_keep_the_typed_name(darkroom: Path) -> None:
    assert canonical_id(darkroom, "camera/2027/2027-01 new") == (
        "Camera/2027/2027-01 new"
    )


@pytest.mark.internal
def test_symlinked_device_is_not_followed(darkroom: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    (outside / "2026").mkdir(parents=True)
    link_dir(darkroom / "Drone", outside)
    assert resolve_path(darkroom, darkroom / "drone" / "2026") == "Drone/2026"


@pytest.mark.internal
@pytest.mark.parametrize(
    ("names", "part", "expected"),
    [
        (["Camera", "camera"], "camera", "camera"),
        (["Camera", "camera"], "CAMERA", "CAMERA"),
        (["Camera", "Phone"], "camera", "Camera"),
        (["Phone"], "camera", "camera"),
    ],
)
def test_on_disk_name_counts_a_unique_match_only(
    names: list[str], part: str, expected: str
) -> None:
    assert on_disk_name(names, part) == expected
