"""Tests for ArchiveAction prepare and execute."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    ArchiveAction,
    Move,
)
from photo_darkroom_manager.core.library import PHOTOS_FOLDER

ARCHIVE_BATCH_BASIC_REL = Path("Camera") / "2026" / "2026-03 archive basic success"
ARCHIVE_BATCH_CONFLICT_REL = (
    Path("Camera") / "2026" / "2026-03 archive will fail on conflict"
)


ARCHIVE_BATCH_BASIC_DEST = Path("2026") / "2026-03 archive basic success" / "Camera"
ARCHIVE_BATCH_CONFLICT_DEST = (
    Path("2026") / "2026-03 archive will fail on conflict" / "Camera"
)


def _relative_leaf_paths(folder: Path) -> frozenset[Path]:
    """Paths of every file under *folder*, relative to *folder*."""
    folder = folder.resolve()
    return frozenset(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())


def _archive(photo_setup, folder: Path) -> ArchiveAction:
    return ArchiveAction(
        folder,
        darkroom=photo_setup.roots.darkroom,
        archive=photo_setup.roots.archive,
    )


def _plan(action: ArchiveAction) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


def test_archive_prepare_happy_batch_root(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    plan = _plan(_archive(photo_setup, batch))
    assert plan.summary == "Archive 4 files"
    assert plan.changes_files
    expected_target = (photo_setup.roots.archive / ARCHIVE_BATCH_BASIC_DEST).resolve()
    rels = _relative_leaf_paths(batch)
    assert {step.target for step in plan.steps if isinstance(step, Move)} == {
        expected_target / rel for rel in rels
    }


def test_archive_prepare_blocked_by_duplicate_in_archive(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_CONFLICT_REL)
    out = _archive(photo_setup, batch).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert "Archive blocked" in out.message


def test_archive_prepare_unrecognized_batch_path(photo_setup) -> None:
    """Path under darkroom but not a batch folder (device/year only) → no batch."""
    year_only = photo_setup.darkroom_has_dir(Path("Camera") / "2026")
    out = _archive(photo_setup, year_only).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert out.message == "Could not recognize batch for this path"


def test_archive_prepare_empty_folder_is_a_noop(photo_setup) -> None:
    empty = photo_setup.roots.darkroom / "Camera" / "2026" / "2026-04 empty"
    empty.mkdir()
    out = _archive(photo_setup, empty).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "noop"


def test_archive_prepare_does_not_create_archive_directories(photo_setup) -> None:
    """Prepare must not mkdir under archive; destination dirs are created on execute."""
    photos = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL / PHOTOS_FOLDER)
    archive_root = photo_setup.roots.archive

    def archive_tree_snapshot() -> frozenset[Path]:
        return frozenset(p.relative_to(archive_root) for p in archive_root.rglob("*"))

    before = archive_tree_snapshot()
    _plan(_archive(photo_setup, photos))
    assert before == archive_tree_snapshot()


def test_archive_prepare_subfolder_photos(photo_setup) -> None:
    """A subfolder (e.g. PHOTOS/) maps to the same subfolder in the archive."""
    photos = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL / PHOTOS_FOLDER)
    plan = _plan(_archive(photo_setup, photos))
    assert len(plan.steps) == 1
    (step,) = plan.steps
    assert isinstance(step, Move)
    expected_rel = ARCHIVE_BATCH_BASIC_DEST / PHOTOS_FOLDER
    assert step.target.parent == (photo_setup.roots.archive / expected_rel).resolve()


def test_archive_execute_moves_all_leaves(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    expected_rels = _relative_leaf_paths(batch)
    act = _archive(photo_setup, batch)
    plan = _plan(act)
    assert len(plan.steps) == len(expected_rels)
    result = act.execute(plan)
    assert result.outcome == "ok"
    assert result.done == plan.steps
    assert f"{len(expected_rels)} of {len(expected_rels)} file" in result.message

    arch_batch = photo_setup.roots.archive / ARCHIVE_BATCH_BASIC_DEST
    for rel in expected_rels:
        assert (arch_batch / rel).is_file()


def test_archive_empties_the_batch(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    act = _archive(photo_setup, batch)
    result = act.execute(_plan(act))
    assert result.outcome == "ok"
    assert not batch.exists()
    assert result.node_path is None
    assert result.left == ()


def test_photo_added_after_the_preview(photo_setup) -> None:
    batch = photo_setup.roots.darkroom / "Camera" / "2026" / "2026-04 two"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"a")
    (batch / "b.jpg").write_bytes(b"b")
    act = _archive(photo_setup, batch)
    plan = _plan(act)
    (batch / "c.jpg").write_bytes(b"c")

    result = act.execute(plan)

    archived = photo_setup.roots.archive / "2026" / "2026-04 two" / "Camera"
    assert (archived / "a.jpg").is_file()
    assert (archived / "b.jpg").is_file()
    assert not (archived / "c.jpg").exists()
    assert (batch / "c.jpg").is_file()
    assert result.outcome == "ok"
    assert [p.name for p in result.left] == ["c.jpg"]
    assert result.node_path == batch
    assert "1 file(s) left" in result.message


def test_partial_archive(photo_setup, monkeypatch: pytest.MonkeyPatch) -> None:
    batch = photo_setup.roots.darkroom / "Camera" / "2026" / "2026-04 three"
    batch.mkdir()
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (batch / name).write_bytes(name.encode())
    act = _archive(photo_setup, batch)
    plan = _plan(act)
    real_move = file_utils.cstm_shutil_move

    def fail_on_c(src, dst, *args, **kwargs):
        if src.endswith("c.jpg"):
            raise PermissionError("file is locked")
        return real_move(src, dst, *args, **kwargs)

    monkeypatch.setattr(file_utils, "cstm_shutil_move", fail_on_c)
    result = act.execute(plan)

    assert result.outcome == "failed"
    assert [s.source.name for s in result.done if isinstance(s, Move)] == [
        "a.jpg",
        "b.jpg",
    ]
    assert len(result.failed) == 1
    failure = result.failed[0]
    assert isinstance(failure.step, Move)
    assert failure.step.source.name == "c.jpg"
    assert "file is locked" in failure.reason
    assert [p.name for p in result.left] == ["c.jpg"]


def test_archive_execute_blocked_when_conflict_appears_after_prepare(
    photo_setup,
) -> None:
    """Prepare passes; a file appears in the archive before execute → no moves."""
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    expected_rels = _relative_leaf_paths(batch)
    block_rel = sorted(expected_rels)[0]
    act = _archive(photo_setup, batch)
    plan = _plan(act)

    block_at = photo_setup.roots.archive / ARCHIVE_BATCH_BASIC_DEST / block_rel
    block_at.parent.mkdir(parents=True, exist_ok=True)
    block_at.write_bytes(b"")

    result = act.execute(plan)
    assert result.outcome == "refused"
    assert result.rescan_node_path is None
    assert "Archive blocked" in result.message
    assert result.details is not None
    assert result.done == ()
    assert (batch / block_rel).exists()


def test_folder_held_open_is_kept_and_reported(
    photo_setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    act = _archive(photo_setup, batch)
    plan = _plan(act)

    def held_open(top: Path) -> None:
        raise PermissionError("folder is in use")

    monkeypatch.setattr(
        "photo_darkroom_manager.core.actions.prune_empty_dirs", held_open
    )
    result = act.execute(plan)

    assert result.outcome == "ok"
    assert result.done == plan.steps
    assert result.details is not None
    assert "folder is in use" in result.details
    assert result.node_path == batch
