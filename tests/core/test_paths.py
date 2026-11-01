from dataclasses import dataclass
from pathlib import Path

import pytest

from photo_darkroom_manager.core.paths import Area, translate_path


@dataclass(frozen=True)
class Roots:
    darkroom: Path = Path("/dr")
    archive: Path = Path("/ar")
    showroom: Path = Path("/sr")


ROOTS = Roots()


@pytest.mark.parametrize("tail", [Path(), Path("PHOTOS/x.raw")])
@pytest.mark.parametrize("dest_area", ["archive", "showroom"])
def test_darkroom_to_destination_and_back(tail: Path, dest_area: Area) -> None:
    source = Path("/dr/Camera/2026/2026-10 Walk") / tail
    dest_root = getattr(ROOTS, dest_area)
    expected = dest_root / "2026" / "2026-10 Walk" / "Camera" / tail
    actual = translate_path(
        source,
        from_area="darkroom",
        from_root=ROOTS.darkroom,
        to_area=dest_area,
        to_root=getattr(ROOTS, dest_area),
    )
    assert actual == expected
    assert (
        translate_path(
            actual,
            from_area=dest_area,
            from_root=getattr(ROOTS, dest_area),
            to_area="darkroom",
            to_root=ROOTS.darkroom,
        )
        == source
    )


def test_showroom_to_archive_changes_only_root() -> None:
    assert translate_path(
        Path("/sr/2026/2026-10 Walk/Camera/PHOTOS/x.raw"),
        from_area="showroom",
        from_root=ROOTS.showroom,
        to_area="archive",
        to_root=ROOTS.archive,
    ) == Path("/ar/2026/2026-10 Walk/Camera/PHOTOS/x.raw")


def test_devices_have_distinct_targets(tmp_path: Path) -> None:
    roots = Roots(tmp_path / "dr", tmp_path / "ar", tmp_path / "sr")
    for device in ("Camera", "Phone"):
        assert (
            translate_path(
                tmp_path / "dr" / device / "2026" / "2026-10 Walk",
                from_area="darkroom",
                from_root=roots.darkroom,
                to_area="archive",
                to_root=roots.archive,
            )
            == tmp_path / "ar" / "2026" / "2026-10 Walk" / device
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "path",
    [
        "/outside/Camera/2026/2026-10 Walk",
        "/dr",
        "/dr/Camera",
        "/dr/Camera/2026",
        "/dr/../Camera/2026/2026-10 Walk",
        "/dr/Camera/2026/2026-10 Walk/../other",
    ],
)
def test_translate_rejects_invalid_paths(path: str) -> None:
    with pytest.raises(ValueError):
        translate_path(
            Path(path),
            from_area="darkroom",
            from_root=ROOTS.darkroom,
            to_area="archive",
            to_root=ROOTS.archive,
        )
