"""Tests for archive: its plan, its question and its run."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.actions import (
    ActionRefusedError,
    archive,
    check_answers,
)
from photo_darkroom_manager.core.actions._moves import CONFLICT_EXISTS
from photo_darkroom_manager.core.jobs import Job, JobCancelled
from photo_darkroom_manager.core.library import PHOTOS_FOLDER

ARCHIVE_BATCH_BASIC_REL = Path("Camera") / "2026" / "2026-03 archive basic success"
ARCHIVE_BATCH_CONFLICT_REL = (
    Path("Camera") / "2026" / "2026-03 archive will fail on conflict"
)
ARCHIVE_BATCH_BASIC_DEST = Path("2026") / "2026-03 archive basic success" / "Camera"


class _CancelAfter(Job):
    """A job that asks itself to stop once *moves* files are done."""

    def __init__(self, moves: int, log_path: Path) -> None:
        super().__init__("archive", log_path=log_path)
        self._moves = moves

    def progress(
        self, done: int, total: int | None = None, current: str | None = None
    ) -> None:
        super().progress(done, total, current)
        if done >= self._moves:
            self.cancel()


def _relative_leaf_paths(folder: Path) -> frozenset[Path]:
    folder = folder.resolve()
    return frozenset(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())


def _prepare(photo_setup, folder: Path) -> archive.ArchivePlan:
    return archive.prepare(
        folder, photo_setup.roots.darkroom, photo_setup.roots.archive
    )


def _run(plan: archive.ArchivePlan, **answers: str) -> archive.ArchiveResult:
    return archive.run(plan, answers, Job("archive"))


def _batch_of(photo_setup, name: str, files: int) -> Path:
    batch = photo_setup.roots.darkroom / "Camera" / "2026" / name
    batch.mkdir()
    for i in range(files):
        (batch / f"{i:03}.jpg").write_bytes(b"new")
    return batch


def _already_archived(photo_setup, name: str, *files: str) -> None:
    archived = photo_setup.roots.archive / "2026" / name / "Camera"
    archived.mkdir(parents=True)
    for file in files:
        (archived / file).write_bytes(b"old")


def test_a_batch_goes_to_its_mapped_location(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    plan = _prepare(photo_setup, batch)
    expected = (photo_setup.roots.archive / ARCHIVE_BATCH_BASIC_DEST).resolve()
    assert plan.target == expected
    assert {m.target for m in plan.moves} == {
        expected / rel for rel in _relative_leaf_paths(batch)
    }
    assert plan.questions == {}


def test_a_subfolder_keeps_its_nested_tail(photo_setup) -> None:
    photos = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL / PHOTOS_FOLDER)
    plan = _prepare(photo_setup, photos)
    (move,) = plan.moves
    expected = photo_setup.roots.archive / ARCHIVE_BATCH_BASIC_DEST / PHOTOS_FOLDER
    assert move.target.parent == expected.resolve()


def test_files_already_archived_are_listed_and_asked_about(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_CONFLICT_REL)
    plan = _prepare(photo_setup, batch)
    assert plan.conflicts
    assert all(c.reason == CONFLICT_EXISTS for c in plan.conflicts)
    assert all(c.target.is_file() for c in plan.conflicts)
    assert not {c.source for c in plan.conflicts} & {m.source for m in plan.moves}
    assert plan.questions[archive.EXISTING_QUESTION].choices == ("skip",)


def test_conflicts_without_an_answer_are_refused(photo_setup) -> None:
    batch = _batch_of(photo_setup, "2026-04 refused", 3)
    _already_archived(photo_setup, "2026-04 refused", "001.jpg")
    plan = _prepare(photo_setup, batch)
    with pytest.raises(ActionRefusedError, match=archive.EXISTING_QUESTION):
        check_answers(plan.questions, {})


def test_skipping_ten_of_a_hundred(photo_setup) -> None:
    batch = _batch_of(photo_setup, "2026-04 hundred", 100)
    taken = [f"{i:03}.jpg" for i in range(0, 100, 10)]
    _already_archived(photo_setup, "2026-04 hundred", *taken)
    plan = _prepare(photo_setup, batch)
    assert len(plan.moves) == 90
    assert len(plan.conflicts) == 10

    result = _run(plan, existing="skip")

    assert result.outcome == "ok"
    assert len(result.moves.moved) == 90
    assert sorted(m.source.name for m in result.moves.skipped) == taken
    assert sorted(p.name for p in batch.iterdir()) == taken
    archived = photo_setup.roots.archive / "2026" / "2026-04 hundred" / "Camera"
    assert len(list(archived.iterdir())) == 100
    assert all((archived / name).read_bytes() == b"old" for name in taken)
    assert "10 skipped" in result.message
    assert not result.source_removed


def test_not_a_batch_is_refused(photo_setup) -> None:
    year = photo_setup.darkroom_has_dir(Path("Camera") / "2026")
    with pytest.raises(ActionRefusedError, match="Could not recognize batch"):
        _prepare(photo_setup, year)


def test_an_empty_folder_has_nothing_to_do(photo_setup) -> None:
    empty = photo_setup.roots.darkroom / "Camera" / "2026" / "2026-04 empty"
    empty.mkdir()
    assert _prepare(photo_setup, empty).nothing_to_do


def test_preparing_creates_no_archive_folder(photo_setup) -> None:
    photos = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL / PHOTOS_FOLDER)
    archive_root = photo_setup.roots.archive
    before = frozenset(archive_root.rglob("*"))
    _prepare(photo_setup, photos)
    assert frozenset(archive_root.rglob("*")) == before


def test_a_whole_batch_is_archived_and_removed(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    expected = _relative_leaf_paths(batch)
    result = _run(_prepare(photo_setup, batch))
    assert result.outcome == "ok"
    assert f"{len(expected)} of {len(expected)} file" in result.message
    assert result.source_removed
    assert not batch.exists()
    archived = photo_setup.roots.archive / ARCHIVE_BATCH_BASIC_DEST
    assert all((archived / rel).is_file() for rel in expected)


def test_a_photo_added_after_the_preview_stays(photo_setup) -> None:
    batch = _batch_of(photo_setup, "2026-04 two", 2)
    plan = _prepare(photo_setup, batch)
    (batch / "late.jpg").write_bytes(b"late")

    result = _run(plan)

    archived = photo_setup.roots.archive / "2026" / "2026-04 two" / "Camera"
    assert len(list(archived.iterdir())) == 2
    assert (batch / "late.jpg").is_file()
    assert result.outcome == "ok"
    assert [p.name for p in result.remaining] == ["late.jpg"]
    assert not result.source_removed
    assert "1 file(s) left" in result.message


def test_a_cancel_lists_the_files_left_undone(photo_setup, tmp_path: Path) -> None:
    batch = _batch_of(photo_setup, "2026-04 four", 4)
    plan = _prepare(photo_setup, batch)
    job = _CancelAfter(2, log_path=tmp_path / "archive.log")

    with pytest.raises(JobCancelled) as stopped:
        archive.run(plan, {}, job)
    job.close()

    result = stopped.value.result
    assert isinstance(result, archive.ArchiveResult)
    assert result.outcome == "cancelled"
    assert [m.source.name for m in result.moves.moved] == ["000.jpg", "001.jpg"]
    assert sorted(m.source.name for m in result.moves.left) == ["002.jpg", "003.jpg"]
    assert sorted(p.name for p in result.remaining) == ["002.jpg", "003.jpg"]
    log = (tmp_path / "archive.log").read_text(encoding="utf-8")
    assert log.count("event='step_done'") == 2


def test_a_failed_file_is_reported_and_remains(
    photo_setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = _batch_of(photo_setup, "2026-04 three", 3)
    plan = _prepare(photo_setup, batch)
    real_move = file_utils.move_file

    def fail_on_last(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "002.jpg":
            raise PermissionError("file is locked")
        real_move(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", fail_on_last)
    result = _run(plan)

    assert result.outcome == "failed"
    assert len(result.moves.moved) == 2
    ((failed),) = result.moves.failed
    assert failed.source.name == "002.jpg"
    assert "file is locked" in (failed.reason or "")
    assert [p.name for p in result.remaining] == ["002.jpg"]


def test_a_file_put_in_the_archive_after_the_preview_is_skipped(photo_setup) -> None:
    batch = _batch_of(photo_setup, "2026-04 late", 3)
    plan = _prepare(photo_setup, batch)
    _already_archived(photo_setup, "2026-04 late", "002.jpg")

    result = _run(plan)

    assert result.outcome == "ok"
    assert [m.source.name for m in result.moves.skipped] == ["002.jpg"]
    assert len(result.moves.moved) == 2
    assert (batch / "002.jpg").read_bytes() == b"new"
    archived = photo_setup.roots.archive / "2026" / "2026-04 late" / "Camera"
    assert (archived / "002.jpg").read_bytes() == b"old"


def test_a_folder_held_open_is_kept_and_reported(
    photo_setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BATCH_BASIC_REL)
    plan = _prepare(photo_setup, batch)

    def held_open(top: Path) -> None:
        raise PermissionError("folder is in use")

    monkeypatch.setattr(archive, "prune_empty_dirs", held_open)
    result = _run(plan)

    assert result.outcome == "ok"
    assert result.moves.moved == plan.moves
    assert "folder is in use" in (result.cleanup_problem or "")
    assert batch.is_dir()
    assert not result.source_removed


def test_preparing_twice_gives_the_same_fingerprint(photo_setup) -> None:
    batch = _batch_of(photo_setup, "2026-04 same", 2)
    first = _prepare(photo_setup, batch).fingerprint
    assert _prepare(photo_setup, batch).fingerprint == first
    (batch / "late.jpg").write_bytes(b"late")
    assert _prepare(photo_setup, batch).fingerprint != first
