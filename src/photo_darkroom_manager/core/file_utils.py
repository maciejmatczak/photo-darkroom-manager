"""Filesystem helpers: safe file moves, empty-folder pruning, merge previews."""

import errno
import os
import shutil
import stat
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

__all__ = [
    "PARTIAL_SUFFIX",
    "CopyMismatchError",
    "MoveOutcome",
    "MoveReport",
    "TargetExistsError",
    "collect_leaf_paths",
    "move_file",
    "move_files",
    "preview_merge_into_archive",
    "prune_empty_dirs",
]

log = structlog.get_logger(__name__)

PARTIAL_SUFFIX = ".darkroom-partial"
"""Suffix of the temporary copy a cross-drive move writes before renaming."""

_RENAME_ATTEMPTS = 5
_RENAME_PAUSE_S = 0.2
_WINERROR_NOT_SAME_DEVICE = 17

Pair = tuple[Path, Path]


class TargetExistsError(FileExistsError):
    """The target holds a file and the move was not asked to replace it."""

    def __init__(self, target: Path) -> None:
        super().__init__(errno.EEXIST, "target already exists", str(target))
        self.target = target


class CopyMismatchError(OSError):
    """A cross-drive copy does not have the size of its source."""

    def __init__(self, source_size: int, copy_size: int) -> None:
        super().__init__(
            f"copy has {copy_size} bytes, source has {source_size}; source kept"
        )


MoveStatus = Literal["done", "skipped", "failed"]


@dataclass(frozen=True, slots=True)
class MoveOutcome:
    """What happened to one requested move, as it finished."""

    source: Path
    target: Path
    status: MoveStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class MoveReport:
    """Which of the requested moves happened, and why the others did not.

    *skipped* holds moves whose target existed at move time (never
    overwritten); *left* holds moves not tried because the run was stopped.
    """

    done: tuple[Pair, ...]
    failed: tuple[tuple[Path, Path, str], ...]
    skipped: tuple[Pair, ...] = ()
    left: tuple[Pair, ...] = ()

    @property
    def cancelled(self) -> bool:
        return bool(self.left)


def _paths_blocking_merge(dest: Path) -> bool:
    """True if *dest* already exists in a way that blocks a file move there."""
    return dest.exists() or dest.is_symlink()


def collect_leaf_paths(source_dir: Path) -> list[Path]:
    """List files and non-directory symlinks under *source_dir* (sorted)."""
    out: list[Path] = []
    for p in sorted(source_dir.rglob("*")):
        if p.is_dir() and not p.is_symlink():
            continue
        out.append(p)
    return out


def _rmdir_empty_dir(path: Path) -> None:
    """Remove an empty directory; no-op if not empty (ENOTEMPTY).

    On other :exc:`OSError`, clear the read-only bit and retry once.
    """
    try:
        path.rmdir()
    except OSError as exc:
        if exc.errno == errno.ENOTEMPTY:
            return
        try:
            os.chmod(path, stat.S_IWRITE)
            path.rmdir()
        except OSError as exc2:
            if exc2.errno == errno.ENOTEMPTY:
                return
            raise exc2 from exc


def prune_empty_dirs(top: Path) -> None:
    """Remove empty directories under *top*, bottom-up; remove *top* if empty last.

    For each walk step, only remove immediate subdirectories (names in ``dirs``).
    Do not call ``root.rmdir()`` inside the walk: that would delete a child
    before the parent's step and leave stale names in ``dirs``. After the walk,
    remove *top* itself if it is now empty.
    """
    top = top.resolve()
    if not top.is_dir():
        return
    for root, dirs, _files in top.walk(top_down=False):
        for name in dirs:
            _rmdir_empty_dir(root / name)
    _rmdir_empty_dir(top)


def preview_merge_into_archive(
    source_dir: Path,
    dest_root: Path,
) -> tuple[tuple[Path, ...], tuple[tuple[Path, Path], ...]]:
    """Resolve paths and compute leaf files plus blocking destination conflicts.

    Does not move files; the archive action plans its moves from the result.
    """
    source_dir = source_dir.resolve()
    dest_root = dest_root.resolve()
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"Source is not a directory: {source_dir}")

    leaves = collect_leaf_paths(source_dir)
    duplicates: list[tuple[Path, Path]] = []
    for src in leaves:
        rel = src.relative_to(source_dir)
        dst = dest_root / rel
        if _paths_blocking_merge(dst):
            duplicates.append((src, dst))

    return tuple(leaves), tuple(duplicates)


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _is_cross_device(error: OSError) -> bool:
    return (
        error.errno == errno.EXDEV
        or getattr(error, "winerror", None) == _WINERROR_NOT_SAME_DEVICE
    )


def _rename(source: Path, target: Path, *, replace: bool) -> None:
    """Rename on one drive; never overwrite unless *replace*.

    ``os.replace`` swaps the target atomically. Without *replace* the target
    is checked first, because POSIX ``rename`` would overwrite it; on
    Windows ``rename`` refuses an existing target by itself.
    """
    if replace:
        os.replace(source, target)
        return
    if _exists(target):
        raise TargetExistsError(target)
    try:
        os.rename(source, target)
    except FileExistsError:
        raise TargetExistsError(target) from None


def _partial_path(target: Path) -> Path:
    return target.with_name(f".{target.name}{PARTIAL_SUFFIX}")


def _copy_times(source: Path, copy: Path) -> None:
    """Copy timestamps and mode as best effort; some shares refuse them."""
    try:
        shutil.copystat(source, copy)
    except OSError as e:
        log.warning("copy_metadata_skipped", source=str(source), error=str(e))


def _rename_into_place(partial: Path, target: Path, *, replace: bool) -> None:
    """Rename the finished copy, retrying while another program holds it.

    An antivirus scan or a NAS indexer can open a new file for a moment,
    which makes the rename fail with a permission error on Windows.
    """
    for attempt in range(1, _RENAME_ATTEMPTS + 1):
        try:
            _rename(partial, target, replace=replace)
            return
        except TargetExistsError:
            raise
        except PermissionError:
            if attempt == _RENAME_ATTEMPTS:
                raise
            time.sleep(_RENAME_PAUSE_S)


def _copy_across(source: Path, target: Path, *, replace: bool) -> None:
    """Move to another drive through a size-checked partial copy.

    The source is removed only once the copy is in place under the target
    name; any failure before that removes the partial copy and keeps the
    source.
    """
    partial = _partial_path(target)
    try:
        shutil.copyfile(source, partial)
        _copy_times(source, partial)
        source_size = source.stat().st_size
        copy_size = partial.stat().st_size
        if copy_size != source_size:
            raise CopyMismatchError(source_size, copy_size)
        _rename_into_place(partial, target, replace=replace)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    source.unlink()


def move_file(source: Path, target: Path, *, replace: bool = False) -> None:
    """Move one file, creating the target folder; never lose either file.

    Without *replace*, an existing target raises :class:`TargetExistsError`
    and both files stay. With *replace*, the old target stays whole until
    the new file takes its place.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if not replace and _exists(target):
        raise TargetExistsError(target)
    try:
        _rename(source, target, replace=replace)
    except TargetExistsError:
        raise
    except OSError as e:
        if not _is_cross_device(e):
            raise
        _copy_across(source, target, replace=replace)


def _reason(error: BaseException) -> str:
    return str(error) or type(error).__name__


def move_files(
    moves: Iterable[Pair],
    *,
    replace: bool = False,
    stop: Callable[[], bool] | None = None,
    on_move: Callable[[MoveOutcome], None] | None = None,
) -> MoveReport:
    """Move each (source, target) file in order, one at a time.

    Keeps going after a failed move and reports it. A target that exists at
    move time is skipped unless *replace*. *stop* is checked before each
    move; once it is true the remaining moves are reported as left.
    *on_move* is called as each move finishes.
    """
    done: list[Pair] = []
    failed: list[tuple[Path, Path, str]] = []
    skipped: list[Pair] = []
    pending = list(moves)
    for index, (src, dst) in enumerate(pending):
        if stop is not None and stop():
            return MoveReport(
                tuple(done), tuple(failed), tuple(skipped), tuple(pending[index:])
            )
        try:
            move_file(src, dst, replace=replace)
        except TargetExistsError:
            skipped.append((src, dst))
            outcome = MoveOutcome(src, dst, "skipped", "target already exists")
        except OSError as e:
            failed.append((src, dst, _reason(e)))
            outcome = MoveOutcome(src, dst, "failed", _reason(e))
        else:
            done.append((src, dst))
            outcome = MoveOutcome(src, dst, "done")
        if on_move is not None:
            on_move(outcome)
    return MoveReport(tuple(done), tuple(failed), tuple(skipped))
