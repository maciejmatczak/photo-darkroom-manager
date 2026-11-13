"""Direct actions: open a folder in the file manager or in an external app.

They run at once with no plan, no confirmation and no job, change no files,
and return their own result. A request that cannot be attempted raises
:class:`ActionRefusedError`; an app that cannot start is a ``failed`` result.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from photo_darkroom_manager.core.library import ALL_IMAGE_EXTENSIONS

from ._base import ActionRefusedError, ActionResult

_EARLY_EXIT_WAIT_S = 0.5
"""How long a started app is watched for an immediate exit with an error."""


@dataclass(frozen=True, kw_only=True)
class OpenFolderResult(ActionResult):
    """Opening a folder in the system file manager.

    Args:
        folder: The folder opened.
    """

    folder: Path


@dataclass(frozen=True, kw_only=True)
class ExternalAppResult(ActionResult):
    """Opening a folder in an external app (cull, edit).

    Args:
        folder: The folder opened.
        command: The program and arguments started.
        exit_code: The app's exit code when it exited at once; ``None``
            while it runs.
    """

    folder: Path
    command: tuple[str, ...]
    exit_code: int | None = None


def _open_in_file_manager(path: Path) -> None:
    """Show *path* in the system file manager."""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_folder(folder: Path) -> OpenFolderResult:
    """Show *folder* in the system file manager; change nothing.

    Raises:
        ActionRefusedError: *folder* does not exist.
    """
    if not folder.is_dir():
        raise ActionRefusedError(f"Folder does not exist: {folder}")
    try:
        _open_in_file_manager(folder)
    except OSError as error:
        return OpenFolderResult(
            outcome="failed",
            message=f"Could not open folder: {folder}: {error}",
            folder=folder,
        )
    return OpenFolderResult(outcome="ok", message=f"Opened {folder}", folder=folder)


def _first_image(folder: Path) -> Path | None:
    """The first image directly in *folder*, by name."""
    try:
        files = [
            f
            for f in folder.iterdir()
            if f.is_file() and f.suffix.lower().lstrip(".") in ALL_IMAGE_EXTENSIONS
        ]
    except PermissionError:
        return None
    return min(files, key=lambda p: p.name) if files else None


class _NoImageFound(Exception):
    pass


class _CommandPlaceholders(dict[str, str]):
    """``{folder}`` and ``{first_image_in_folder}`` for one folder."""

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self._folder = folder.resolve()

    def __missing__(self, key: str) -> str:
        if key == "folder":
            return str(self._folder)
        if key == "first_image_in_folder":
            first = _first_image(self._folder)
            if first is None:
                raise _NoImageFound
            return str(first.resolve())
        raise KeyError(key)


def _strip_outer_shell_quotes(part: str) -> str:
    """Drop one pair of outer quotes from a token.

    ``shlex.split(..., posix=False)`` (used so Windows paths keep ``\\``)
    leaves surrounding ``"`` or ``'`` inside the token; a program's argument
    list must not include them.
    """
    if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
        return part[1:-1]
    return part


def _resolve_command(template: str, folder: Path) -> tuple[str, ...]:
    """The program and arguments *template* stands for on *folder*.

    Raises:
        ActionRefusedError: The command is empty, has an unknown placeholder
            or bad quoting, or needs a first image the folder lacks.
    """
    if not template.strip():
        raise ActionRefusedError("Command is empty")
    try:
        resolved = template.format_map(_CommandPlaceholders(folder))
    except _NoImageFound:
        raise ActionRefusedError(
            "No image found in folder",
            "{first_image_in_folder} requires an image file as a direct child of "
            "the folder (not inside subfolders such as PHOTOS/).",
        ) from None
    except KeyError as error:
        raise ActionRefusedError("Unknown placeholder in command", str(error)) from None
    except ValueError as error:
        raise ActionRefusedError("Invalid command template", str(error)) from None
    try:
        parts = shlex.split(resolved, posix=False)
    except ValueError as error:
        raise ActionRefusedError("Invalid command (quoting)", str(error)) from None
    if not parts:
        raise ActionRefusedError("Command resolves to empty")
    return tuple(_strip_outer_shell_quotes(part) for part in parts)


def open_external_app(command: str, folder: Path) -> ExternalAppResult:
    """Start the external app *command* on *folder*; change nothing.

    In *command*, ``{folder}`` stands for the folder and
    ``{first_image_in_folder}`` for the first image directly in it, by name.

    Raises:
        ActionRefusedError: *folder* does not exist, or the command cannot
            be resolved (see :func:`_resolve_command`).
    """
    if not folder.is_dir():
        raise ActionRefusedError(f"Folder does not exist: {folder}")
    argv = _resolve_command(command, folder)
    try:
        process = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError as error:
        return ExternalAppResult(
            outcome="failed",
            message=f"Could not start command: {list(argv)}: {error}",
            folder=folder,
            command=argv,
        )
    try:
        exit_code = process.wait(timeout=_EARLY_EXIT_WAIT_S)
    except subprocess.TimeoutExpired:
        return ExternalAppResult(
            outcome="ok",
            message="Started external application",
            folder=folder,
            command=argv,
        )
    if exit_code == 0:
        return ExternalAppResult(
            outcome="ok",
            message="Started external application",
            folder=folder,
            command=argv,
            exit_code=0,
        )
    return ExternalAppResult(
        outcome="failed",
        message=f"Command exited with code {exit_code}",
        folder=folder,
        command=argv,
        exit_code=exit_code,
    )
