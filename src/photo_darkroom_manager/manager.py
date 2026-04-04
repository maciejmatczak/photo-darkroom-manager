"""DarkroomManager -- settings, scan tree, and action dispatch."""

from __future__ import annotations

from pathlib import Path

from photo_darkroom_manager.actions import (
    Action,
    ArchiveAction,
    NewAlbumAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.scan import DarkroomNode, scan_darkroom
from photo_darkroom_manager.settings import Settings


class DarkroomManager:
    def __init__(self, settings: Settings) -> None:
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

    def tidy_action(self, folder_path: Path) -> Action:
        return TidyAction(folder_path)

    def archive_action(self, folder_path: Path) -> Action:
        return ArchiveAction(folder_path, self.settings.darkroom, self.settings.archive)

    def publish_action(self, album_path: Path) -> Action:
        return PublishAction(album_path, self.settings.showroom, self.settings.darkroom)

    def rename_action(self, album_path: Path, new_name: str) -> Action:
        return RenameAction(album_path, new_name, self.settings.darkroom)

    def new_album_action(
        self, year: str, month: str, day: str | None, name: str
    ) -> Action:
        return NewAlbumAction(self.settings.darkroom, year, month, day, name)
