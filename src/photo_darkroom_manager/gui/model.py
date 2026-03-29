"""Application state -- holds scan tree and dispatches actions."""

from __future__ import annotations

import traceback
from pathlib import Path

from photo_darkroom_manager.gui.actions import (
    ActionResult,
    action_archive,
    action_new_album,
    action_publish,
    action_rename_album,
    action_tidy,
)
from photo_darkroom_manager.gui.config import GuiSettings
from photo_darkroom_manager.gui.scanner import DarkroomNode, scan_darkroom


def _safe(fn, *args, **kwargs) -> ActionResult:
    """Call *fn* and return its ActionResult; on unhandled exception return a
    failure result so the GUI never crashes silently."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        return ActionResult(False, f"Unexpected error:\n{traceback.format_exc()}")


class App:
    def __init__(self, settings: GuiSettings) -> None:
        self.settings = settings
        self.tree: DarkroomNode | None = None
        self.scanning = False

    def rescan(self) -> DarkroomNode:
        self.scanning = True
        try:
            self.tree = scan_darkroom(self.settings.darkroom)
        finally:
            self.scanning = False
        return self.tree

    def new_album(
        self, year: str, month: str, day: str | None, name: str
    ) -> ActionResult:
        return _safe(action_new_album, self.settings.darkroom, year, month, day, name)

    def tidy(self, folder_path: Path) -> ActionResult:
        return _safe(action_tidy, folder_path)

    def archive(self, folder_path: Path) -> ActionResult:
        return _safe(
            action_archive,
            folder_path,
            self.settings.darkroom,
            self.settings.archive,
        )

    def publish(self, album_path: Path) -> ActionResult:
        return _safe(
            action_publish,
            album_path,
            self.settings.showroom,
            self.settings.darkroom,
        )

    def rename_album(self, album_path: Path, new_name: str) -> ActionResult:
        return _safe(action_rename_album, album_path, new_name, self.settings.darkroom)
