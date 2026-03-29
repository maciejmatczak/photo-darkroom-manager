"""Filesystem helpers (moves, permissions, and related reporting)."""

import os
import shutil
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MoveIssue",
    "cstm_shutil_move",
    "make_remove_readonly_onexc",
    "move_dir_safely",
]


@dataclass(frozen=True, slots=True)
class MoveIssue:
    """One problem encountered during a directory move."""

    stage: str
    operation: str
    path: Path
    error: BaseException
    recovered: bool = False


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
            issues.append(MoveIssue("rmtree", func.__name__, p, exc, recovered=False))
            issues.append(MoveIssue("rmtree", func.__name__, p, exc2, recovered=False))
            raise exc2
        else:
            issues.append(MoveIssue("rmtree", func.__name__, p, exc, recovered=True))

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
        if shutil._samefile(src, dst) and not os.path.islink(src):
            # We might be on a case insensitive filesystem,
            # perform the rename anyway.
            os.rename(src, dst)
            return real_dst

        # Using _basename instead of os.path.basename is important, as we must
        # ignore any trailing slash to avoid the basename returning ''
        real_dst = os.path.join(dst, shutil._basename(src))

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
            if shutil._destinsrc(src, dst):
                raise shutil.Error(
                    f"Cannot move a directory {src!r} into itself {dst!r}."
                ) from None
            if shutil._is_immutable(src) or (
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


def move_dir_safely(source_dir: Path, target_dir: Path) -> tuple[Path, list[MoveIssue]]:
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"Source directory is not a directory: {source_dir}")
    if target_dir.exists():
        raise ValueError(f"Target directory already exists: {target_dir}")
    move_issues: list[MoveIssue] = []
    dest = cstm_shutil_move(
        source_dir,
        target_dir,
        onexc=make_remove_readonly_onexc(move_issues),
        issues=move_issues,
    )
    return Path(dest), move_issues
