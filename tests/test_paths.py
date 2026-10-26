from pathlib import Path

import pytest

from photo_darkroom_manager.paths import translate_path


@pytest.mark.parametrize("tail", [Path(), Path("PHOTOS/x.raw")])
def test_translate_path_reorders_and_round_trips(tail: Path) -> None:
    source = Path("/dr/Camera/2026/2026-10 Walk") / tail
    expected = Path("/ar/2026/2026-10 Walk/Camera") / tail
    actual = translate_path(
        source,
        from_root=Path("/dr"),
        to_root=Path("/ar"),
        from_layout="device-first",
        to_layout="batch-first",
    )
    assert actual == expected
    assert (
        translate_path(
            actual,
            from_root=Path("/ar"),
            to_root=Path("/dr"),
            from_layout="batch-first",
            to_layout="device-first",
        )
        == source
    )


def test_same_layout_preserves_relative_path() -> None:
    assert translate_path(
        Path("/ar/2026/2026-10 Walk/Camera/PHOTOS/x.raw"),
        from_root=Path("/ar"),
        to_root=Path("/sr"),
        from_layout="batch-first",
        to_layout="batch-first",
    ) == Path("/sr/2026/2026-10 Walk/Camera/PHOTOS/x.raw")


def test_devices_have_distinct_targets(tmp_path: Path) -> None:
    for device in ("Camera", "Phone"):
        assert (
            translate_path(
                tmp_path / "dr" / device / "2026" / "2026-10 Walk",
                from_root=tmp_path / "dr",
                to_root=tmp_path / "ar",
                from_layout="device-first",
                to_layout="batch-first",
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
            from_root=Path("/dr"),
            to_root=Path("/ar"),
            from_layout="device-first",
            to_layout="batch-first",
        )
