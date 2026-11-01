"""Filesystem helpers (moves, permissions, and related reporting)."""

import errno
import os
import shutil
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ArchiveMergeResult",
    "MoveIssue",
    "cstm_shutil_move",
    "make_remove_readonly_onexc",
    "merge_tree_into_archive",
    "preview_merge_into_archive",
]


@dataclass(frozen=True, slots=True)
class MoveIssue:
    """One problem encountered during a directory move."""

    stage: str
    operation: str
    path: Path
    error: BaseException
    recovered: bool = False


@dataclass(frozen=True, slots=True)
class ArchiveMergeResult:
    """Outcome of merging a source tree into an archive destination."""

    moved_files: int
    duplicates: tuple[tuple[Path, Path], ...]
    issues: tuple[MoveIssue, ...]


def _paths_blocking_merge(dest: Path) -> bool:
    """True if *dest* already exists in a way that blocks a file move there."""
    return dest.exists() or dest.is_symlink()


def _collect_leaf_paths_to_move(source_dir: Path) -> list[Path]:
    """List files and non-directory symlinks under *source_dir* (sorted)."""
    out: list[Path] = []
    for p in sorted(source_dir.rglob("*")):
        if p.is_dir() and not p.is_symlink():
            continue
        out.append(p)
    return out


def _rmdir_empty_dir(path: Path) -> None:
    """Remove an empty directory; no-op if not empty (ENOTEMPTY).

    On other :exc:`OSError`, clear the read-only bit and retry once (same idea as
    :func:`make_remove_readonly_onexc`).
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


def _prune_empty_dirs_under(top: Path) -> None:
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

    Does not move files. Used by :func:`merge_tree_into_archive` and the GUI
    prepare step so preview and execute stay aligned.
    """
    source_dir = source_dir.resolve()
    dest_root = dest_root.resolve()
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"Source is not a directory: {source_dir}")

    leaves = _collect_leaf_paths_to_move(source_dir)
    duplicates: list[tuple[Path, Path]] = []
    for src in leaves:
        rel = src.relative_to(source_dir)
        dst = dest_root / rel
        if _paths_blocking_merge(dst):
            duplicates.append((src, dst))

    return tuple(leaves), tuple(duplicates)


def merge_tree_into_archive(
    source_dir: Path,
    dest_root: Path,
) -> ArchiveMergeResult:
    """Move every file under *source_dir* into *dest_root*, preserving relative paths.

    Creates *dest_root* and intermediate dirs as needed. If any destination path
    would be overwritten (including broken symlinks at the destination), no
    files are moved and *duplicates* lists each (src, dest) pair.

    After successful moves, removes empty directories under *source_dir*,
    including *source_dir* when empty. Uses :func:`cstm_shutil_move` per file for
    cross-filesystem semantics.
    """

    # potentially this can be swapped out with rclone move

    source_dir = source_dir.resolve()
    dest_root = dest_root.resolve()
    leaves, duplicates = preview_merge_into_archive(source_dir, dest_root)

    if duplicates:
        return ArchiveMergeResult(0, duplicates, ())

    # this shenanigans were needed when moving whole directory
    # (we had there rmtree issue on source cleanup)
    # not sure if the are still needed here (moving files only)
    move_issues: list[MoveIssue] = []
    onexc = make_remove_readonly_onexc(move_issues)
    moved = 0
    for src in leaves:
        rel = src.relative_to(source_dir)
        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            cstm_shutil_move(
                str(src),
                str(dst),
                onexc=onexc,
                issues=move_issues,
            )
        except (OSError, shutil.Error) as e:
            move_issues.append(
                MoveIssue("merge", "cstm_shutil_move", src, e, recovered=False)
            )
        else:
            moved += 1

    _prune_empty_dirs_under(source_dir)

    return ArchiveMergeResult(moved, (), tuple(move_issues))


def make_remove_readonly_onexc(
    issues: list[MoveIssue],
) -> Callable[[Callable[..., object], str, BaseException], None]:
    """Build an ``onexc`` handler for ``shutil.rmtree`` that clears read-only bits.

    Records each initial failure and whether ``chmod`` + retry fixed it, or the
    retry error if not.
    """

    def onexc(func: Callable[..., object], path: str, exc: BaseException) -> None:
        p = Path(path)
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError as exc2:
            op = getattr(func, "__name__", "<callable>")
            issues.append(MoveIssue("rmtree", op, p, exc, recovered=False))
            issues.append(MoveIssue("rmtree", op, p, exc2, recovered=False))
            raise exc2
        else:
            issues.append(
                MoveIssue(
                    "rmtree",
                    getattr(func, "__name__", "<callable>"),
                    p,
                    exc,
                    recovered=True,
                )
            )

    return onexc


def cstm_shutil_move(
    src,
    dst,
    copy_function=shutil.copy2,
    onexc=None,
    issues: list[MoveIssue] | None = None,
):
    """Recursively move a file or directory to another location. This is
    similar to the Unix "mv" command. Return the file or directory's
    destination.

    If dst is an existing directory or a symlink to a directory, then src is
    moved inside that directory. The destination path in that directory must
    not already exist.

    If dst already exists but is not a directory, it may be overwritten
    depending on os.rename() semantics.

    If the destination is on our current filesystem, then rename() is used.
    Otherwise, src is copied to the destination and then removed. Symlinks are
    recreated under the new name if os.rename() fails because of cross
    filesystem renames.

    The optional `copy_function` argument is a callable that will be used
    to copy the source or it will be delegated to `copytree`.
    By default, copy2() is used, but any function that supports the same
    signature (like copy()) can be used.

    A lot more could be done here...  A look at a mv.c shows a lot of
    the issues this implementation glosses over.

    """
    real_dst = dst
    if os.path.isdir(dst):
        if shutil._samefile(src, dst) and not os.path.islink(src):  # ty: ignore[unresolved-attribute]
            # We might be on a case insensitive filesystem,
            # perform the rename anyway.
            os.rename(src, dst)
            return real_dst

        # Using _basename instead of os.path.basename is important, as we must
        # ignore any trailing slash to avoid the basename returning ''
        real_dst = os.path.join(dst, shutil._basename(src))  # ty: ignore[unresolved-attribute]

        if os.path.exists(real_dst):
            raise shutil.Error(f"Destination path {real_dst!r} already exists")
    try:
        os.rename(src, real_dst)
    except OSError:
        if os.path.islink(src):
            linkto = os.readlink(src)
            os.symlink(linkto, real_dst)
            os.unlink(src)
        elif os.path.isdir(src):
            if shutil._destinsrc(src, dst):  # ty: ignore[unresolved-attribute]
                raise shutil.Error(
                    f"Cannot move a directory {src!r} into itself {dst!r}."
                ) from None
            if shutil._is_immutable(src) or (  # ty: ignore[unresolved-attribute]
                not os.access(src, os.W_OK)
                and os.listdir(src)
                and sys.platform == "darwin"
            ):
                raise PermissionError(
                    "Cannot move the non-empty directory "
                    f"{src!r}: Lacking write permission to {src!r}."
                ) from None
            try:
                shutil.copytree(
                    src, real_dst, copy_function=copy_function, symlinks=True
                )
            except (OSError, shutil.Error) as e:
                if issues is not None:
                    issues.append(
                        MoveIssue(
                            "copytree",
                            "copytree",
                            Path(src),
                            e,
                            recovered=False,
                        )
                    )
                raise
            shutil.rmtree(src, onexc=onexc)
        else:
            copy_function(src, real_dst)
            os.unlink(src)
    return real_dst
