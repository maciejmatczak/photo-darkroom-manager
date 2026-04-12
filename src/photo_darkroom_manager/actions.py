"""Core action logic -- prepare/execute plans for tidy, archive, publish, albums."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from photo_darkroom_manager.file_utils import (
    merge_tree_into_archive,
    preview_merge_into_archive,
)
from photo_darkroom_manager.media import (
    ALL_IMAGE_EXTENSIONS,
    is_file_a_photo,
    is_file_a_video,
)
from photo_darkroom_manager.models import recognize_darkroom_album
from photo_darkroom_manager.settings import (
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    VIDEOS_FOLDER,
)

_PREVIEW_PATH_LINES = 35


def _format_preview_path_names(
    root: Path, paths: tuple[Path, ...], *, max_lines: int
) -> str:
    lines: list[str] = []
    for i, p in enumerate(paths):
        if i >= max_lines:
            lines.append(f"… and {len(paths) - max_lines} more")
            break
        lines.append(f"  {p.relative_to(root)}")
    return "\n".join(lines)


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

    pass


class ActionPlan:
    def preview_text(self) -> str:
        raise NotImplementedError


class Action(ABC):
    """Template method: public prepare/execute never raise.

    Subclasses implement _prepare / _execute.
    """

    def prepare(self) -> ActionPlan | PrepareError | None:
        try:
            return self._prepare()
        except Exception:
            return PrepareError(False, "Internal error", traceback.format_exc())

    def execute(self, plan: ActionPlan | None) -> ExecutionResult:
        try:
            return self._execute(plan)
        except Exception:
            return ExecutionResult(
                False, "Internal error", details=traceback.format_exc()
            )

    @abstractmethod
    def _prepare(self) -> ActionPlan | PrepareError | None: ...

    @abstractmethod
    def _execute(self, plan: ActionPlan | None) -> ExecutionResult: ...


def _collect_files_to_tidy(folder: Path) -> tuple[list[Path], list[Path]]:
    """Collect misplaced photos and videos in a single directory.

    Groups files by stem so sidecars move together. Uses correct-state predicate:
    photos belong in PHOTOS/, videos in VIDEOS/.
    """
    seen_stems: set[str] = set()
    photo_paths: list[Path] = []
    video_paths: list[Path] = []

    try:
        items = folder.iterdir()
    except PermissionError:
        return [], []

    for item in items:
        if not item.is_file():
            continue
        stem = item.name.split(".")[0]
        if stem in seen_stems:
            continue
        seen_stems.add(stem)

        all_related = list(folder.glob(f"{stem}.*"))
        suffixes = [f.name.split(".", 1)[-1] for f in all_related]

        if (
            is_file_a_photo(suffixes)
            and not is_file_a_video(suffixes)
            and folder.name != PHOTOS_FOLDER
        ):
            photo_paths.extend(all_related)
        elif (
            is_file_a_video(suffixes)
            and not is_file_a_photo(suffixes)
            and folder.name != VIDEOS_FOLDER
        ):
            video_paths.extend(all_related)

    return photo_paths, video_paths


def collect_files_to_tidy(
    folder_path: Path, *, recursive: bool = False
) -> tuple[list[Path], list[Path]]:
    """Collect misplaced photos and videos under folder_path.

    Skips PUBLISH/ entirely. When recursive=True, walks all subdirectories.
    """
    if PUBLISH_FOLDER in folder_path.parts:
        return [], []

    photo_paths, video_paths = _collect_files_to_tidy(folder_path)

    if recursive:
        try:
            children = sorted(folder_path.iterdir())
        except PermissionError:
            return photo_paths, video_paths
        for child in children:
            if child.is_dir() and child.name != PUBLISH_FOLDER:
                p, v = collect_files_to_tidy(child, recursive=True)
                photo_paths.extend(p)
                video_paths.extend(v)

    return photo_paths, video_paths


@dataclass(frozen=True)
class TidyPlan(ActionPlan):
    folder_path: Path
    photo_paths: tuple[Path, ...]
    video_paths: tuple[Path, ...]

    def preview_text(self) -> str:
        n_photo = len(self.photo_paths)
        n_video = len(self.video_paths)
        parts = [
            f"Root folder: {self.folder_path}",
            "",
            f"Photos to move: {n_photo}",
            f"Videos to move: {n_video}",
            "",
        ]
        if n_photo:
            parts.append("Photo files (-> PHOTOS/):")
            parts.append(
                _format_preview_path_names(
                    self.folder_path, self.photo_paths, max_lines=_PREVIEW_PATH_LINES
                )
            )
        if n_video:
            parts.append("Video files (-> VIDEOS/):")
            parts.append(
                _format_preview_path_names(
                    self.folder_path, self.video_paths, max_lines=_PREVIEW_PATH_LINES
                )
            )
        return "\n".join(parts)


class TidyAction(Action):
    def __init__(self, folder_path: Path) -> None:
        self._folder_path = folder_path

    def _prepare(self) -> TidyPlan | PrepareError:
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return PrepareError(False, f"Not a directory: {folder_path}")

        photo_paths, video_paths = collect_files_to_tidy(folder_path, recursive=True)
        if not photo_paths and not video_paths:
            details = "\n".join(
                [
                    f"Folder: {folder_path}",
                    "Photos to move: 0",
                    "Videos to move: 0",
                ]
            )
            return PrepareError(False, "Nothing to tidy", details)
        return TidyPlan(
            folder_path=folder_path,
            photo_paths=tuple(photo_paths),
            video_paths=tuple(video_paths),
        )

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if not isinstance(plan, TidyPlan):
            return ExecutionResult(False, "Internal error: invalid plan for tidy")
        folder_path = plan.folder_path

        moved = 0
        if plan.photo_paths:
            photos_dir = folder_path / PHOTOS_FOLDER
            photos_dir.mkdir(exist_ok=True)
            for p in plan.photo_paths:
                shutil.move(str(p), str(photos_dir / p.name))
                moved += 1

        if plan.video_paths:
            videos_dir = folder_path / VIDEOS_FOLDER
            videos_dir.mkdir(exist_ok=True)
            for p in plan.video_paths:
                shutil.move(str(p), str(videos_dir / p.name))
                moved += 1

        return ExecutionResult(True, f"Tidied {moved} files")


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
        darkroom_path: Path,
        archive_path: Path,
    ) -> None:
        self._folder_path = folder_path
        self._darkroom_path = darkroom_path
        self._archive_path = archive_path

    def _prepare(self) -> ArchivePlan | PrepareError:
        folder_path = self._folder_path
        album = recognize_darkroom_album(self._darkroom_path, folder_path)
        if album is None:
            return PrepareError(False, "Could not recognize album for this path")

        target_dir = self._archive_path / album.relative_subpath
        target_dir.parent.mkdir(parents=True, exist_ok=True)

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
            return ExecutionResult(False, "Internal error: invalid plan for archive")
        try:
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
            )

        return ExecutionResult(
            True,
            f"Archived {merge_result.moved_files} file(s) to {plan.target_dir}",
        )


@dataclass(frozen=True)
class PublishPlan(ActionPlan):
    album_path: Path
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
            f"Album: {self.album_path.relative_to(self.darkroom_path)}",
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
        album_path: Path,
        showroom_path: Path,
        darkroom_path: Path,
    ) -> None:
        self._album_path = album_path
        self._showroom_path = showroom_path
        self._darkroom_path = darkroom_path

    def _prepare(self) -> PublishPlan | PrepareError:
        album_path = self._album_path
        album = recognize_darkroom_album(self._darkroom_path, album_path)
        if album is None:
            return PrepareError(False, "Could not recognize album")

        publish_dir = album_path / PUBLISH_FOLDER
        if not publish_dir.exists():
            return PrepareError(False, "PUBLISH directory does not exist")

        files = [f for f in publish_dir.iterdir() if f.is_file()]
        if not files:
            return PrepareError(False, "PUBLISH directory is empty")

        dirs_in_publish = [f for f in publish_dir.iterdir() if f.is_dir()]
        if dirs_in_publish:
            return PrepareError(False, "PUBLISH directory contains subdirectories")

        target_dir = self._showroom_path / album.year / album.album
        conflicts: list[tuple[Path, Path]] = []
        for f in files:
            dest = target_dir / f.name
            if dest.exists():
                conflicts.append((f, dest))

        return PublishPlan(
            album_path=album_path,
            showroom_path=self._showroom_path,
            darkroom_path=self._darkroom_path,
            files=tuple(files),
            target_dir=target_dir,
            conflict_pairs=tuple(conflicts),
        )

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if not isinstance(plan, PublishPlan):
            return ExecutionResult(False, "Internal error: invalid plan for publish")
        plan.target_dir.mkdir(parents=True, exist_ok=True)

        moved = 0
        for f in plan.files:
            dest = plan.target_dir / f.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(f), str(dest))
            moved += 1

        return ExecutionResult(True, f"Published {moved} files to showroom")


class NewAlbumAction(Action):
    def __init__(
        self,
        darkroom_path: Path,
        year: str,
        month: str,
        day: str | None,
        name: str,
    ) -> None:
        self._darkroom_path = darkroom_path
        self._year = year
        self._month = month
        self._day = day
        self._name = name

    def _prepare(self) -> ActionPlan | PrepareError | None:
        return None

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if plan is not None:
            return ExecutionResult(False, "Internal error: new album expects no plan")
        darkroom_path = self._darkroom_path
        year = self._year
        month = self._month
        day = self._day
        name = self._name

        date_part = f"{year}-{month}"
        if day:
            date_part = f"{date_part}-{day}"
        album_folder_name = f"{date_part} {name.strip()}" if name.strip() else date_part

        target_dir = darkroom_path / year / album_folder_name
        if target_dir.exists():
            return ExecutionResult(False, f"Album folder already exists: {target_dir}")

        target_dir.mkdir(parents=True, exist_ok=False)
        publish_dir = target_dir / PUBLISH_FOLDER
        publish_dir.mkdir(parents=True, exist_ok=True)

        return ExecutionResult(True, f"Created album: {album_folder_name}")


class RenameAction(Action):
    def __init__(
        self,
        album_path: Path,
        new_name: str,
        darkroom_path: Path,
    ) -> None:
        self._album_path = album_path
        self._new_name = new_name
        self._darkroom_path = darkroom_path

    def _prepare(self) -> ActionPlan | PrepareError | None:
        return None

    def _execute(self, plan: ActionPlan | None) -> ExecutionResult:
        if plan is not None:
            return ExecutionResult(False, "Internal error: rename expects no plan")
        album_path = self._album_path
        new_name = self._new_name
        darkroom_path = self._darkroom_path

        album = recognize_darkroom_album(darkroom_path, album_path)
        if album is None:
            return ExecutionResult(False, "Could not recognize album")

        new_name_stripped = new_name.strip()
        if not new_name_stripped:
            return ExecutionResult(False, "New name cannot be empty")

        new_path = album_path.parent / new_name_stripped
        if new_path.exists():
            return ExecutionResult(
                False, f"A folder named '{new_name_stripped}' already exists"
            )

        album_path.rename(new_path)
        return ExecutionResult(True, f"Renamed to {new_name_stripped}")


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
            return ExecutionResult(True, "Started external application")

        if code == 0:
            return ExecutionResult(True, "Started external application")

        return ExecutionResult(
            False,
            f"Command exited with code {code}",
            details=None,
        )
