"""Tests for library layout models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from photo_darkroom_manager.core.library import (
    PUBLISH_FOLDER,
    BatchFolderName,
    DarkroomBatch,
    NodeKind,
    child_kind,
    recognize_darkroom_batch,
)


@pytest.mark.internal
@pytest.mark.parametrize(
    ("parent", "name", "kind"),
    [
        ("root", "Camera", "device"),
        ("root", "2026", "device"),
        ("device", "2026", "year"),
        ("device", "Misc", None),
        ("device", "26", None),
        ("year", "2026-10 Walk", "batch"),
        ("year", "2026-10", "batch"),
        ("year", "Undated", None),
        ("batch", PUBLISH_FOLDER, "publish"),
        ("batch", "PHOTOS", "subfolder"),
        ("publish", "extra", "subfolder"),
        ("subfolder", PUBLISH_FOLDER, "subfolder"),
    ],
)
def test_child_kind(parent: NodeKind, name: str, kind: NodeKind | None) -> None:
    assert child_kind(parent, name) == kind


def test_darkroom_year_batch_valid() -> None:
    p = Path("/dr/Camera/2024/2024-01 Batch")
    a = DarkroomBatch(
        device="Camera",
        year="2024",
        batch="2024-01 Batch",
        batch_path=p,
        relative_subpath=Path("Camera/2024/2024-01 Batch"),
    )
    assert a.year == "2024"
    assert a.publish_dir == p / PUBLISH_FOLDER


def test_darkroom_year_batch_valid_with_day() -> None:
    p = Path("/dr/Camera/2026/2026-04-15 Spring Outing")
    a = DarkroomBatch(
        device="Camera",
        year="2026",
        batch="2026-04-15 Spring Outing",
        batch_path=p,
        relative_subpath=Path("2026/2026-04-15 Spring Outing"),
    )
    assert a.batch == "2026-04-15 Spring Outing"


@pytest.mark.parametrize(
    "year",
    ["abcd", "24", "20245"],
)
def test_darkroom_year_batch_invalid_year(year: str) -> None:
    batch = "2024-01 x"
    with pytest.raises(ValidationError, match="year"):
        DarkroomBatch(
            device="Camera",
            year=year,
            batch=batch,
            batch_path=Path("/dr") / "Camera" / year / batch,
            relative_subpath=Path("Camera") / year / batch,
        )


@pytest.mark.parametrize(
    "batch",
    ["01 Batch", "foo", "2024-1 x"],
)
def test_darkroom_year_batch_invalid_batch_format(batch: str) -> None:
    year = "2024"
    with pytest.raises(ValidationError, match="batch"):
        DarkroomBatch(
            device="Camera",
            year=year,
            batch=batch,
            batch_path=Path("/dr") / "Camera" / year / batch,
            relative_subpath=Path("Camera") / year / batch,
        )


def test_darkroom_year_batch_rejects_non_calendar_month() -> None:
    """Invalid month (not 01–12) is rejected."""
    p = Path("/dr/Camera/2024/2024-13 Batch")
    with pytest.raises(ValidationError, match="batch"):
        DarkroomBatch(
            device="Camera",
            year="2024",
            batch="2024-13 Batch",
            batch_path=p,
            relative_subpath=Path("Camera/2024/2024-13 Batch"),
        )


def test_darkroom_year_batch_rejects_glued_suffix_after_month() -> None:
    """Characters glued after YYYY-MM without a space are rejected."""
    p = Path("/dr/Camera/2024/2024-01foo")
    with pytest.raises(ValidationError, match="batch"):
        DarkroomBatch(
            device="Camera",
            year="2024",
            batch="2024-01foo",
            batch_path=p,
            relative_subpath=Path("Camera/2024/2024-01foo"),
        )


def test_recognize_darkroom_batch_happy_path() -> None:
    dr = Path("/dr")
    path = dr / "Camera" / "2024" / "2024-01 Test"
    batch = recognize_darkroom_batch(dr, path)
    assert batch is not None
    assert batch.year == "2024"
    assert batch.batch == "2024-01 Test"
    assert batch.batch_path == path
    assert batch.relative_subpath == Path("Camera/2024/2024-01 Test")


def test_recognize_darkroom_batch_deeper_subpath() -> None:
    dr = Path("/dr")
    path = dr / "Camera" / "2024" / "2024-01 A" / "PHOTOS" / "nested"
    batch = recognize_darkroom_batch(dr, path)
    assert batch is not None
    assert batch.relative_subpath == Path("Camera/2024/2024-01 A/PHOTOS/nested")
    assert batch.batch_path == dr / "Camera" / "2024" / "2024-01 A"


@pytest.mark.parametrize("rel", ["", "Camera", "Camera/2024"])
def test_recognize_darkroom_batch_too_shallow_returns_none(
    tmp_path: Path, rel: str
) -> None:
    dr = tmp_path / "dr"
    assert recognize_darkroom_batch(dr, dr / rel) is None


@pytest.mark.parametrize("rel", ["Camera/24/2024-01", "Camera/2024/not a batch"])
def test_recognize_darkroom_batch_invalid_component_raises(
    tmp_path: Path, rel: str
) -> None:
    dr = tmp_path / "dr"
    with pytest.raises(ValueError):
        recognize_darkroom_batch(dr, dr / rel)


def test_recognize_darkroom_batch_not_under_darkroom_raises(tmp_path: Path) -> None:
    dr = tmp_path / "dr"
    other = tmp_path / "other"
    dr.mkdir()
    other.mkdir()
    with pytest.raises(ValueError, match="not a subpath"):
        recognize_darkroom_batch(dr, other)


def test_batch_folder_name_round_trip_date_only() -> None:
    a = BatchFolderName(year="2024", month="01", day=None, name=None)
    assert a.folder_name == "2024-01"
    p = BatchFolderName.from_str(a.folder_name)
    assert p.year == "2024"
    assert p.month == "01"
    assert p.day is None
    assert p.name is None


def test_batch_folder_name_round_trip_with_day_and_title() -> None:
    a = BatchFolderName(year="2026", month="04", day="15", name="Spring Outing")
    assert a.folder_name == "2026-04-15 Spring Outing"
    p = BatchFolderName.from_str(a.folder_name)
    assert p.folder_name == a.folder_name


def test_batch_folder_name_normalizes_month_and_day() -> None:
    a = BatchFolderName(year="2024", month="4", day="5", name=None)
    assert a.month == "04"
    assert a.day == "05"
    assert a.folder_name == "2024-04-05"


def test_batch_folder_name_from_str_raises_for_invalid_shape() -> None:
    with pytest.raises(ValidationError):
        BatchFolderName.from_str("not-a-date")
    with pytest.raises(ValidationError):
        BatchFolderName.from_str("2024-01foo")


def test_batch_folder_name_from_str_raises_when_values_invalid() -> None:
    with pytest.raises(ValidationError):
        BatchFolderName.from_str("2024-13-01")


def test_batch_folder_name_rejects_forbidden_title_chars() -> None:
    with pytest.raises(ValidationError):
        BatchFolderName(year="2024", month="01", day=None, name="bad:name")
