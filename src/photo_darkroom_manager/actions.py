"""Core action logic -- prepare/execute plans for tidy, archive, publish, batches."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import traceback
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import structlog
from pydantic import ValidationError

from photo_darkroom_manager.file_utils import (
    merge_tree_into_archive,
    preview_merge_into_archive,
)
from photo_darkroom_manager.library import (
    ALL_IMAGE_EXTENSIONS,
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    VIDEOS_FOLDER,
    BatchFolderName,
    NodeId,
    collect_files_to_tidy,
    format_validation_error,
    is_file_a_photo,
    is_file_a_video,
    recognize_darkroom_batch,
    validate_device_name,
)
from photo_darkroom_manager.paths import translate_path

_PREVIEW_PATH_LINES = 35

log = structlog.get_logger(__name__)


def _file_extension(path: Path) -> str:
    return path.suffix.lstrip(".").lower()


def _tidy_destination(src: Path) -> Path:
    """Resolve target path for a misplaced media file."""
    parent = src.parent
    ext = _file_extension(src)

    if parent.name == PHOTOS_FOLDER and is_file_a_video([ext]):
        return parent.parent / VIDEOS_FOLDER / src.name
    if parent.name == VIDEOS_FOLDER and is_file_a_photo([ext]):
        return parent.parent / PHOTOS_FOLDER / src.name
    if is_file_a_video([ext]):
        return parent / VIDEOS_FOLDER / src.name
    return parent / PHOTOS_FOLDER / src.name


def _build_tidy_moves(folder_path: Path) -> list[tuple[Path, Path]]:
    """Collect misplaced files recursively and pair each with its tidy target.

    Targets are per source folder (e.g. iPhone/IMG.jpg → iPhone/PHOTOS/), not
    flattened to the action root, so prepare, preview, and execute share one plan.
    """
    photo_paths, video_paths = collect_files_to_tidy(folder_path, recursive=True)
    sources = photo_paths + video_paths
    return [(src, _tidy_destination(src)) for src in sources]


def _find_tidy_conflicts(
    moves: Sequence[tuple[Path, Path]],
) -> list[tuple[Path, Path]]:
    """Return moves that would overwrite an existing file or another move's target.

    Checked at prepare and again at execute so the user sees conflicts before
    confirming and late arrivals on disk cannot silently replace files.
    """
    conflicts: list[tuple[Path, Path]] = []
    seen_dst: dict[Path, Path] = {}

    for src, dst in moves:
        if dst in seen_dst and seen_dst[dst] != src:
            conflicts.append((src, dst))
        else:
            seen_dst[dst] = src

        if (
            dst.exists()
            and dst.resolve() != src.resolve()
            and (src, dst) not in conflicts
        ):
            conflicts.append((src, dst))

    return conflicts


def _format_tidy_move_lines(root: Path, pairs: Sequence[tuple[Path, Path]]) -> str:
    lines = [
        f"{src.relative_to(root)}\n\t→ {dst.relative_to(root)}" for src, dst in pairs
    ]
    return "\n".join(lines)


def _format_extension_stats(paths: Sequence[Path]) -> str:
    counts = Counter(f".{_file_extension(p)}" for p in paths)
    return "\n".join(f"  {ext}: {n}" for ext, n in sorted(counts.items()))


def _unavailable_root(**roots: Path) -> str | None:
    """Message for the first library root that is not a folder, if any.

    Actions check their roots themselves at prepare and execute: a root
    validated earlier may be gone by now (e.g. an unplugged drive).
    """
    for name, root in roots.items():
        if not root.is_dir():
            return f"{name.capitalize()} folder is not available: {root}"
    return None


@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str
    details: str | None = None


@dataclass(frozen=True)
class PrepareError(ActionResult):
    """Prepare step failed before an executable plan was produced."""

    pass


@dataclass(frozen=True)
class ExecutionResult(ActionResult):
    """Result of executing an action after user confirmation."""

    rescan_node_path: Path | None = None
    """Subtree root to rescan after this action; None means no rescan needed."""
    library_refreshed: NodeId | None = None
    """Id the engine rescanned after the action; None when it rescanned nothing."""


class ActionPlan:
    def preview_text(self) -> str:
        raise NotImplementedError


class Action(ABC):
    """Template method: public prepare/execute never raise.

    Subclasses implement _prepare / _execute.
    """

    def log_context(self) -> dict[str, object]:
        return {}

    def prepare(self) -> ActionPlan | PrepareError | None:
        action_name = type(self).__name__
        ctx = self.log_context()
        try:
            result = self._prepare()
        except Exception:
            log.exception("action_prepare", action=action_name, **ctx)
            return PrepareError(False, "Internal error", traceback.format_exc())

        if isinstance(result, PrepareError):
            log.warning(
                "action_prepare",
                action=action_name,
                success=False,
                message=result.message,
                **ctx,
            )
        elif result is None:
            log.info(
                "action_prepare",
                action=action_name,
                success=True,
                message="no plan",
                **ctx,
            )
        else:
            log.info(
                "action_prepare",
                action=action_name,
                success=True,
                message="plan ready",
                **ctx,
            )
        return result

    def execute(self, plan: ActionPlan | None) -> ExecutionResult:
        action_name = type(self).__name__
        ctx = self.log_context()
        try:
            result = self._execute(plan)
        except Exception:
            log.exception("action_execute", action=action_name, **ctx)
            return ExecutionResult(
                False, "Internal error", details=traceback.format_exc()
            )

        if result.success:
            log.info(
                "action_execute",
                action=action_name,
                success=True,
                message=result.message,
                **ctx,
            )
        else:
            log.warning(
                "action_execute",
                action=action_name,
                success=False,
                message=result.message,
                **ctx,
            )
        return result

    @abstractmethod
    def _prepare(self) -> ActionPlan | PrepareError | None: ...

    @abstractmethod
    def _execute(self, plan: ActionPlan | None) -> ExecutionResult: ...


@dataclass(frozen=True)
class TidyPlan(ActionPlan):
    folder_path: Path
    moves: tuple[tuple[Path, Path], ...]

    def preview_text(self) -> str:
        photo_sources = [
            src for src, dst in self.moves if dst.parent.name == PHOTOS_FOLDER
        ]
        video_sources = [
            src for src, dst in self.moves if dst.parent.name == VIDEOS_FOLDER
        ]
        n_photo = len(photo_sources)
        n_video = len(video_sources)
        parts = [
            f"Root folder: {self.folder_path}",
            "",
            f"Photos to move: {n_photo}",
            f"Videos to move: {n_video}",
            "",
        ]
        if n_photo:
            parts.append("Photos:")
            parts.append(_format_extension_stats(photo_sources))
        if n_video:
            parts.append("Videos:")
            parts.append(_format_extension_stats(video_sources))
        return "\n".join(parts)


class TidyAction(Action):
    def __init__(self, folder_path: Path) -> None:
        self._folder_path = folder_path

    def log_context(self) -> dict[str, object]:
        return {"folder": str(self._folder_path)}

    def _prepare(self) -> TidyPlan | PrepareError:
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return PrepareError(False, f"Not a directory: {folder_path}")

        moves = _build_tidy_moves(folder_path)
        if not moves:
            details = "\n".join(
                [
                    f"Folder: {folder_path}",
                    "Photos to move: 0",
                    "Videos to move: 0",
                ]
            )
            return PrepareError(False, "Nothing to tidy", details)

        conflicts = _find_tidy_conflicts(moves)
        if conflicts:
            return PrepareError(
                False,
                f"Tidy blocked: {len(conflicts)} file conflict(s)",
                _format_tidy_move_lines(folder_path, conflicts),
            )

        return TidyPlan(folder_path=folder_path, moves=tuple(moves))

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if not isinstance(plan, TidyPlan):
            return ExecutionResult(
                False,
                "Internal error: invalid plan for tidy",
            )
        if not plan.folder_path.is_dir():
            return ExecutionResult(False, f"Not a directory: {plan.folder_path}")

        conflicts = _find_tidy_conflicts(plan.moves)
        if conflicts:
            return ExecutionResult(
                False,
                f"Tidy blocked: {len(conflicts)} file conflict(s)",
                details=_format_tidy_move_lines(plan.folder_path, conflicts),
            )

        for src, dst in plan.moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

        return ExecutionResult(
            True,
            f"Tidied {len(plan.moves)} files",
            rescan_node_path=plan.folder_path,
        )


@dataclass(frozen=True)
class ArchivePlan(ActionPlan):
    folder_path: Path
    target_dir: Path
    darkroom_path: Path
    archive_path: Path
    leaf_count: int

    def preview_text(self) -> str:
        parts = [
            f"Darkroom: {self.darkroom_path}",
            f"Archive: {self.archive_path}",
            "",
            f" Source: {self.folder_path.relative_to(self.darkroom_path)}",
            "",
            f"Archive: {self.target_dir.relative_to(self.archive_path)}",
            "",
            f"Files to move: {self.leaf_count}",
        ]
        return "\n".join(parts)


class ArchiveAction(Action):
    def __init__(
        self,
        folder_path: Path,
        *,
        darkroom: Path,
        archive: Path,
    ) -> None:
        self._folder_path = folder_path
        self._darkroom_path = darkroom
        self._archive_path = archive

    def _unavailable_root(self) -> str | None:
        return _unavailable_root(
            darkroom=self._darkroom_path, archive=self._archive_path
        )

    def log_context(self) -> dict[str, object]:
        return {"folder": str(self._folder_path)}

    def _prepare(self) -> ArchivePlan | PrepareError:
        if problem := self._unavailable_root():
            return PrepareError(False, problem)
        folder_path = self._folder_path
        batch = recognize_darkroom_batch(self._darkroom_path, folder_path)
        if batch is None:
            return PrepareError(False, "Could not recognize batch for this path")

        target_dir = translate_path(
            folder_path,
            from_area="darkroom",
            from_root=self._darkroom_path,
            to_area="archive",
            to_root=self._archive_path,
        )

        try:
            leaves, duplicates = preview_merge_into_archive(folder_path, target_dir)
        except ValueError as e:
            return PrepareError(False, str(e))

        if duplicates:
            lines = [
                f"{src.relative_to(self._darkroom_path)}"
                f"\n\t→ {dst.relative_to(self._archive_path)}"
                for src, dst in duplicates
            ]
            return PrepareError(
                False,
                f"Archive blocked: {len(duplicates)} file conflict(s)"
                "already in archive",
                "\n".join(lines),
            )

        return ArchivePlan(
            folder_path=folder_path,
            target_dir=target_dir,
            darkroom_path=self._darkroom_path,
            archive_path=self._archive_path,
            leaf_count=len(leaves),
        )

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if not isinstance(plan, ArchivePlan):
            return ExecutionResult(
                False,
                "Internal error: invalid plan for archive",
            )
        if problem := self._unavailable_root():
            return ExecutionResult(False, problem)
        try:
            plan.target_dir.parent.mkdir(parents=True, exist_ok=True)
            merge_result = merge_tree_into_archive(plan.folder_path, plan.target_dir)
        except ValueError as e:
            return ExecutionResult(False, str(e))

        if merge_result.duplicates:
            lines = [
                f"{src.relative_to(self._darkroom_path)}"
                f"\n\t→ {dst.relative_to(self._archive_path)}"
                for src, dst in merge_result.duplicates
            ]

            return ExecutionResult(
                False,
                f"Archive blocked: {len(merge_result.duplicates)} file conflict(s)"
                "already in archive",
                details="\n".join(lines),
            )

        unrecovered = [i for i in merge_result.issues if not i.recovered]
        if unrecovered:
            details = "\n".join(
                f"{i.operation} {i.path}: {i.error}" for i in unrecovered
            )
            return ExecutionResult(
                False,
                "Archive finished with errors (see details)",
                details=details,
                rescan_node_path=self._folder_path.parent,
            )

        return ExecutionResult(
            True,
            f"Archived {merge_result.moved_files} file(s) to {plan.target_dir}",
            rescan_node_path=self._folder_path.parent,
        )


@dataclass(frozen=True)
class PublishPlan(ActionPlan):
    batch_path: Path
    showroom_path: Path
    darkroom_path: Path
    files: tuple[Path, ...]
    target_dir: Path
    conflict_pairs: tuple[tuple[Path, Path], ...]

    def preview_text(self) -> str:
        n_conf = len(self.conflict_pairs)
        parts = [
            f"Darkroom: {self.darkroom_path}",
            f"Showroom: {self.showroom_path}",
            "",
            f"Batch: {self.batch_path.relative_to(self.darkroom_path)}",
            f"Showroom: {self.target_dir.relative_to(self.showroom_path)}",
            "",
            f"Files to publish: {len(self.files)}",
            f"Target directory exists: {self.target_dir.exists()}",
            "",
        ]
        if n_conf:
            parts.append(f"WARNING: {n_conf} file conflict(s) will be overwritten")
            lines = [
                f"  {src.name} → {dst}"
                for src, dst in self.conflict_pairs[:_PREVIEW_PATH_LINES]
            ]
            parts.append("\n".join(lines))
            if n_conf > _PREVIEW_PATH_LINES:
                parts.append(f"… and {n_conf - _PREVIEW_PATH_LINES} more")
        return "\n".join(parts)


class PublishAction(Action):
    def __init__(
        self,
        batch_path: Path,
        *,
        darkroom: Path,
        showroom: Path,
    ) -> None:
        self._batch_path = batch_path
        self._showroom_path = showroom
        self._darkroom_path = darkroom

    def _unavailable_root(self) -> str | None:
        return _unavailable_root(
            darkroom=self._darkroom_path, showroom=self._showroom_path
        )

    def log_context(self) -> dict[str, object]:
        return {"batch": str(self._batch_path)}

    def _prepare(self) -> PublishPlan | PrepareError:
        if problem := self._unavailable_root():
            return PrepareError(False, problem)
        batch_path = self._batch_path
        batch = recognize_darkroom_batch(self._darkroom_path, batch_path)
        if batch is None:
            return PrepareError(False, "Could not recognize batch")

        publish_dir = batch_path / PUBLISH_FOLDER
        if not publish_dir.exists():
            return PrepareError(False, "PUBLISH directory does not exist")

        files = [f for f in publish_dir.iterdir() if f.is_file()]
        if not files:
            return PrepareError(False, "PUBLISH directory is empty")

        dirs_in_publish = [f for f in publish_dir.iterdir() if f.is_dir()]
        if dirs_in_publish:
            return PrepareError(False, "PUBLISH directory contains subdirectories")

        target_dir = translate_path(
            batch.batch_path,
            from_area="darkroom",
            from_root=self._darkroom_path,
            to_area="showroom",
            to_root=self._showroom_path,
        )
        conflicts: list[tuple[Path, Path]] = []
        for f in files:
            dest = target_dir / f.name
            if dest.exists():
                conflicts.append((f, dest))

        return PublishPlan(
            batch_path=batch_path,
            showroom_path=self._showroom_path,
            darkroom_path=self._darkroom_path,
            files=tuple(files),
            target_dir=target_dir,
            conflict_pairs=tuple(conflicts),
        )

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if not isinstance(plan, PublishPlan):
            return ExecutionResult(
                False,
                "Internal error: invalid plan for publish",
            )
        if problem := self._unavailable_root():
            return ExecutionResult(False, problem)
        plan.target_dir.mkdir(parents=True, exist_ok=True)

        moved = 0
        for f in plan.files:
            dest = plan.target_dir / f.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(f), str(dest))
            moved += 1

        return ExecutionResult(
            True,
            f"Published {moved} files to showroom",
            rescan_node_path=self._batch_path,
        )


class NewBatchAction(Action):
    def __init__(
        self,
        darkroom_path: Path,
        device: str,
        year: str,
        month: str,
        day: str | None,
        name: str | None,
    ) -> None:
        self._darkroom_path = darkroom_path
        self._device = device
        self._year = year
        self._month = month
        self._day = day
        self._name = name

    def log_context(self) -> dict[str, object]:
        return {
            "darkroom": str(self._darkroom_path),
            "device": self._device,
            "year": self._year,
            "month": self._month,
        }

    def _prepare(self) -> ActionPlan | PrepareError | None:
        if problem := _unavailable_root(darkroom=self._darkroom_path):
            return PrepareError(False, problem)
        return None

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if plan is not None:
            return ExecutionResult(
                False,
                "Internal error: new batch expects no plan",
            )
        if problem := _unavailable_root(darkroom=self._darkroom_path):
            return ExecutionResult(False, problem)
        darkroom_path = self._darkroom_path
        year = self._year
        month = self._month
        day = self._day
        name = self._name

        try:
            device = validate_device_name(self._device)
            batch_folder_name = BatchFolderName(
                year=year, month=month, day=day, name=name
            ).folder_name
        except ValidationError as e:
            return ExecutionResult(
                False,
                format_validation_error(e),
            )
        except ValueError as e:
            return ExecutionResult(False, str(e))

        target_dir = darkroom_path / device / year / batch_folder_name
        if not target_dir.resolve().is_relative_to(darkroom_path.resolve()):
            return ExecutionResult(False, "Batch path must remain inside darkroom")
        if target_dir.exists():
            return ExecutionResult(
                False,
                f"Batch folder already exists: {target_dir}",
            )

        try:
            target_dir.mkdir(parents=True, exist_ok=False)
            (target_dir / PUBLISH_FOLDER).mkdir()
        except OSError as e:
            return ExecutionResult(False, f"Could not create batch folder: {e}")

        return ExecutionResult(
            True,
            f"Created batch: {batch_folder_name}",
            # TODO: this rescans the whole year; ideally only the new batch
            # node would be added without a full year subtree walk.
            rescan_node_path=target_dir.parent,
        )


class RenameAction(Action):
    def __init__(
        self,
        batch_path: Path,
        darkroom_path: Path,
        year: str,
        month: str,
        day: str | None,
        name: str | None,
    ) -> None:
        self._batch_path = batch_path
        self._darkroom_path = darkroom_path
        self._year = year
        self._month = month
        self._day = day
        self._name = name

    def log_context(self) -> dict[str, object]:
        return {"batch": str(self._batch_path)}

    def _prepare(self) -> ActionPlan | PrepareError | None:
        if problem := _unavailable_root(darkroom=self._darkroom_path):
            return PrepareError(False, problem)
        return None

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if plan is not None:
            return ExecutionResult(
                False,
                "Internal error: rename expects no plan",
            )
        if problem := _unavailable_root(darkroom=self._darkroom_path):
            return ExecutionResult(False, problem)
        batch_path = self._batch_path
        darkroom_path = self._darkroom_path
        year = self._year
        month = self._month
        day = self._day
        name = self._name

        if recognize_darkroom_batch(darkroom_path, batch_path) is None:
            return ExecutionResult(
                False,
                "Could not recognize batch",
            )

        try:
            new_folder_name = BatchFolderName(
                year=year, month=month, day=day, name=name
            ).folder_name
        except ValidationError as e:
            return ExecutionResult(
                False,
                format_validation_error(e),
            )

        if new_folder_name == batch_path.name:
            return ExecutionResult(
                True,
                f"No change: {new_folder_name}",
            )

        new_path = batch_path.parent / new_folder_name
        if new_path.exists():
            return ExecutionResult(
                False,
                f"A folder named '{new_folder_name}' already exists",
            )

        batch_path.rename(new_path)
        return ExecutionResult(
            True,
            f"Renamed to {new_folder_name}",
            rescan_node_path=batch_path.parent,
        )


class _NoImageFound(Exception):
    pass


def _find_first_image(folder: Path) -> Path | None:
    try:
        files = [
            f
            for f in folder.iterdir()
            if f.is_file() and f.suffix.lower().lstrip(".") in ALL_IMAGE_EXTENSIONS
        ]
    except PermissionError:
        return None
    if not files:
        return None
    return min(files, key=lambda p: p.name)


class _CommandMapping(dict[str, str]):
    def __init__(self, folder: Path) -> None:
        super().__init__()
        self._folder = folder.resolve()

    def __missing__(self, key: str) -> str:
        if key == "folder":
            return str(self._folder)
        if key == "first_image_in_folder":
            first = _find_first_image(self._folder)
            if first is None:
                raise _NoImageFound
            return str(first.resolve())
        raise KeyError(key)


def _strip_outer_shell_quotes(part: str) -> str:
    """Drop one pair of outer quotes from a shlex token.

    ``shlex.split(..., posix=False)`` (used so Windows paths keep ``\\``) leaves
    surrounding ``"`` or ``'`` inside the token; ``subprocess`` argv must not
    include those characters.
    """
    if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
        return part[1:-1]
    return part


def _resolve_command(template: str, folder: Path) -> list[str] | PrepareError:
    if not template.strip():
        return PrepareError(False, "Command is empty", None)
    mapping = _CommandMapping(folder)
    try:
        resolved = template.format_map(mapping)
    except _NoImageFound:
        return PrepareError(
            False,
            "No image found in folder",
            details=(
                "{first_image_in_folder} requires an image file as a direct child of "
                "the folder (not inside subfolders such as PHOTOS/)."
            ),
        )
    except KeyError as e:
        return PrepareError(
            False,
            "Unknown placeholder in command",
            details=str(e),
        )
    except ValueError as e:
        return PrepareError(False, "Invalid command template", details=str(e))

    try:
        parts = shlex.split(resolved, posix=False)
    except ValueError as e:
        return PrepareError(False, "Invalid command (quoting)", details=str(e))

    if not parts:
        return PrepareError(False, "Command resolves to empty", None)

    return [_strip_outer_shell_quotes(p) for p in parts]


class OpenExternalAppAction(Action):
    def __init__(self, command_template: str, folder_path: Path) -> None:
        self._command_template = command_template
        self._folder_path = folder_path

    def log_context(self) -> dict[str, object]:
        return {"folder": str(self._folder_path)}

    def _prepare(self) -> ActionPlan | PrepareError | None:
        outcome = _resolve_command(self._command_template, self._folder_path)
        if isinstance(outcome, PrepareError):
            return outcome
        return None

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        outcome = _resolve_command(self._command_template, self._folder_path)
        if isinstance(outcome, PrepareError):
            return ExecutionResult(
                False,
                outcome.message,
                details=outcome.details,
            )
        parts = outcome
        try:
            proc = subprocess.Popen(
                parts,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError) as e:
            return ExecutionResult(
                False,
                f"Could not start command: {parts}",
                details=str(e),
            )

        try:
            code = proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                True,
                "Started external application",
            )

        if code == 0:
            return ExecutionResult(
                True,
                "Started external application",
            )

        return ExecutionResult(
            False,
            f"Command exited with code {code}",
        )
