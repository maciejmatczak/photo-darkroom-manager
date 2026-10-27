"""DarkroomManager -- settings, scan tree, and action dispatch."""

from __future__ import annotations

import time
from pathlib import Path

import structlog

from photo_darkroom_manager.actions import (
    Action,
    ArchiveAction,
    NewBatchAction,
    OpenExternalAppAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.paths import translate_path
from photo_darkroom_manager.scan import (
    DarkroomNode,
    reaggregate_ancestors,
    rescan_subtree,
    scan_darkroom,
)
from photo_darkroom_manager.settings import Settings

log = structlog.get_logger(__name__)


def _scan_stats(node: DarkroomNode) -> tuple[int, int]:
    """Return (batch_count, nodes_with_issues_count) for a scan tree."""
    batches = 1 if node.node_type == "batch" else 0
    issues = 1 if node.issues else 0
    for child in node.children:
        child_batches, child_issues = _scan_stats(child)
        batches += child_batches
        issues += child_issues
    return batches, issues


def _require_one(*args: Path | None) -> None:
    if sum(1 for a in args if a is not None) != 1:
        raise ValueError("Provide exactly one non-None path argument")


class DarkroomManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.tree: DarkroomNode | None = None
        self.scanning = False

    def rescan_subtree(self, node: DarkroomNode) -> DarkroomNode:
        """Rescan *node* in place and reaggregate ancestors. Returns *node*.

        Preferred over ``rescan()`` when only a single subtree has changed
        (e.g. after a tidy or publish action).  I/O is limited to the node's
        subtree; ancestor stats/issues are re-aggregated cheaply without disk
        access.
        """
        log.info("rescan_subtree_started", path=str(node.path))
        started = time.perf_counter()
        rescan_subtree(node)
        reaggregate_ancestors(node)
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "rescan_subtree_complete", path=str(node.path), duration_ms=duration_ms
        )
        return node

    def rescan(self) -> DarkroomNode:
        root = self.settings.darkroom
        log.info("rescan_started", root=str(root))
        started = time.perf_counter()
        self.scanning = True
        try:
            self.tree = scan_darkroom(root)
        finally:
            self.scanning = False
        batches, issues = _scan_stats(self.tree)
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "rescan_complete",
            root=str(root),
            batches=batches,
            issues=issues,
            duration_ms=duration_ms,
        )
        return self.tree

    def tidy_action(self, folder_path: Path) -> Action:
        return TidyAction(folder_path)

    def open_external_app_action(
        self, command_template: str, folder_path: Path
    ) -> Action:
        return OpenExternalAppAction(command_template, folder_path)

    def archive_action(self, folder_path: Path) -> Action:
        return ArchiveAction(folder_path, self.settings)

    def publish_action(self, batch_path: Path) -> Action:
        return PublishAction(batch_path, self.settings)

    def rename_action(
        self, batch_path: Path, year: str, month: str, day: str | None, name: str | None
    ) -> Action:
        return RenameAction(batch_path, self.settings.darkroom, year, month, day, name)

    def new_batch_action(
        self, device: str, year: str, month: str, day: str | None, name: str | None
    ) -> Action:
        return NewBatchAction(self.settings.darkroom, device, year, month, day, name)

    def list_devices(self) -> list[str]:
        """Discover current device directories, including empty ones."""
        return sorted(p.name for p in self.settings.darkroom.iterdir() if p.is_dir())

    def darkroom_path(
        self,
        *,
        archive_path: Path | None = None,
        showroom_path: Path | None = None,
    ) -> Path:
        _require_one(archive_path, showroom_path)
        if archive_path is not None:
            return translate_path(
                archive_path,
                roots=self.settings,
                from_area="archive",
                to_area="darkroom",
            )
        assert showroom_path is not None
        return translate_path(
            showroom_path,
            roots=self.settings,
            from_area="showroom",
            to_area="darkroom",
        )

    def showroom_path(
        self,
        *,
        darkroom_path: Path | None = None,
        archive_path: Path | None = None,
    ) -> Path:
        _require_one(darkroom_path, archive_path)
        if darkroom_path is not None:
            return translate_path(
                darkroom_path,
                roots=self.settings,
                from_area="darkroom",
                to_area="showroom",
            )
        assert archive_path is not None
        return translate_path(
            archive_path,
            roots=self.settings,
            from_area="archive",
            to_area="showroom",
        )

    def archive_path(
        self,
        *,
        darkroom_path: Path | None = None,
        showroom_path: Path | None = None,
    ) -> Path:
        _require_one(darkroom_path, showroom_path)
        if darkroom_path is not None:
            return translate_path(
                darkroom_path,
                roots=self.settings,
                from_area="darkroom",
                to_area="archive",
            )
        assert showroom_path is not None
        return translate_path(
            showroom_path,
            roots=self.settings,
            from_area="showroom",
            to_area="archive",
        )
