"""Tests for ArchiveAction prepare and execute."""

from pathlib import Path

from photo_darkroom_manager.actions import ArchiveAction, ArchivePlan, PrepareError
from photo_darkroom_manager.settings import PHOTOS_FOLDER

ARCHIVE_ALBUM_BASIC_REL = Path("2026") / "2026-03 archive basic success"
ARCHIVE_ALBUM_CONFLICT_REL = Path("2026") / "2026-03 archive will fail on conflict"


def _relative_leaf_paths(folder: Path) -> frozenset[Path]:
    """Paths of every file under *folder*, relative to *folder*."""
    folder = folder.resolve()
    return frozenset(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())


def test_archive_prepare_happy_album_root(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(ARCHIVE_ALBUM_BASIC_REL)
    act = ArchiveAction(
        album,
        photo_setup.settings.darkroom,
        photo_setup.settings.archive,
    )
    out = act._prepare()
    assert isinstance(out, ArchivePlan)
    assert out.leaf_count == 4
    assert out.folder_path == album
    expected_target = (photo_setup.settings.archive / ARCHIVE_ALBUM_BASIC_REL).resolve()
    assert out.target_dir == expected_target


def test_archive_prepare_blocked_by_duplicate_in_archive(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(ARCHIVE_ALBUM_CONFLICT_REL)
    act = ArchiveAction(
        album,
        photo_setup.settings.darkroom,
        photo_setup.settings.archive,
    )
    out = act._prepare()
    assert isinstance(out, PrepareError)
    assert not out.success
    assert "Archive blocked" in out.message


def test_archive_prepare_unrecognized_album_path(photo_setup) -> None:
    """Path under darkroom but not an album folder (year only) → no album."""
    year_only = photo_setup.darkroom_has_dir(Path("2026"))
    act = ArchiveAction(
        year_only,
        photo_setup.settings.darkroom,
        photo_setup.settings.archive,
    )
    out = act._prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "Could not recognize album for this path"


def test_archive_prepare_subfolder_photos(photo_setup) -> None:
    """UI can pass a subfolder (e.g. PHOTOS/); relative_subpath includes it."""
    photos = photo_setup.darkroom_has_dir(ARCHIVE_ALBUM_BASIC_REL / PHOTOS_FOLDER)
    act = ArchiveAction(
        photos,
        photo_setup.settings.darkroom,
        photo_setup.settings.archive,
    )
    out = act._prepare()
    assert isinstance(out, ArchivePlan)
    assert out.leaf_count == 1
    expected_rel = ARCHIVE_ALBUM_BASIC_REL / PHOTOS_FOLDER
    assert out.target_dir == (photo_setup.settings.archive / expected_rel).resolve()


def test_archive_execute_moves_all_leaves(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(ARCHIVE_ALBUM_BASIC_REL)
    expected_rels = _relative_leaf_paths(album)
    act = ArchiveAction(
        album,
        photo_setup.settings.darkroom,
        photo_setup.settings.archive,
    )
    plan = act._prepare()
    assert isinstance(plan, ArchivePlan)
    assert plan.leaf_count == len(expected_rels)
    result = act._execute(plan)
    assert result.success
    assert f"{len(expected_rels)} file" in result.message

    arch_album = photo_setup.settings.archive / ARCHIVE_ALBUM_BASIC_REL
    for rel in expected_rels:
        assert (arch_album / rel).is_file()


def test_archive_execute_blocked_when_conflict_appears_after_prepare(
    photo_setup,
) -> None:
    """Prepare passes; a file appears in the archive before execute → no moves."""
    album = photo_setup.darkroom_has_dir(ARCHIVE_ALBUM_BASIC_REL)
    expected_rels = _relative_leaf_paths(album)
    block_rel = sorted(expected_rels)[0]
    act = ArchiveAction(
        album,
        photo_setup.settings.darkroom,
        photo_setup.settings.archive,
    )
    plan = act._prepare()
    assert isinstance(plan, ArchivePlan)

    block_at = photo_setup.settings.archive / ARCHIVE_ALBUM_BASIC_REL / block_rel
    block_at.parent.mkdir(parents=True, exist_ok=True)
    block_at.write_bytes(b"")

    result = act._execute(plan)
    assert not result.success
    assert "Archive blocked" in result.message
    assert result.details is not None

    assert (album / block_rel).exists()
