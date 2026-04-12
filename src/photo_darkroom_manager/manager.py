"""DarkroomManager -- settings, scan tree, and action dispatch."""

from __future__ import annotations

from pathlib import Path

from photo_darkroom_manager.actions import (
    Action,
    ArchiveAction,
    NewAlbumAction,
    OpenExternalAppAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.scan import DarkroomNode, scan_darkroom
from photo_darkroom_manager.settings import Settings


def _translate_path(path: Path, from_root: Path, to_root: Path) -> Path:
    return to_root / path.relative_to(from_root)


def _require_one(*args: Path | None) -> None:
    if sum(1 for a in args if a is not None) != 1:
        raise ValueError("Provide exactly one non-None path argument")


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

    def open_external_app_action(
        self, command_template: str, folder_path: Path
    ) -> Action:
        return OpenExternalAppAction(command_template, folder_path)

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

    def darkroom_path(
        self,
        *,
        archive_path: Path | None = None,
        showroom_path: Path | None = None,
    ) -> Path:
        _require_one(archive_path, showroom_path)
        if archive_path is not None:
            return _translate_path(
                archive_path, self.settings.archive, self.settings.darkroom
            )
        assert showroom_path is not None
        return _translate_path(
            showroom_path, self.settings.showroom, self.settings.darkroom
        )

    def showroom_path(
        self,
        *,
        darkroom_path: Path | None = None,
        archive_path: Path | None = None,
    ) -> Path:
        _require_one(darkroom_path, archive_path)
        if darkroom_path is not None:
            return _translate_path(
                darkroom_path, self.settings.darkroom, self.settings.showroom
            )
        assert archive_path is not None
        return _translate_path(
            archive_path, self.settings.archive, self.settings.showroom
        )

    def archive_path(
        self,
        *,
        darkroom_path: Path | None = None,
        showroom_path: Path | None = None,
    ) -> Path:
        _require_one(darkroom_path, showroom_path)
        if darkroom_path is not None:
            return _translate_path(
                darkroom_path, self.settings.darkroom, self.settings.archive
            )
        assert showroom_path is not None
        return _translate_path(
            showroom_path, self.settings.showroom, self.settings.archive
        )
