"""NiceGUI layout: header bar, recursive expansion tree, action buttons."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from nicegui import run, ui

from photo_darkroom_manager.actions import (
    Action,
    ActionPlan,
    ActionResult,
    ExecutionResult,
    PrepareError,
)
from photo_darkroom_manager.manager import DarkroomManager
from photo_darkroom_manager.scan import DarkroomNode
from photo_darkroom_manager.settings import PUBLISH_FOLDER

# ---------------------------------------------------------------------------
# Shared style tokens -- single source of truth for recurring props/classes
# ---------------------------------------------------------------------------
CSS_TREE_BTN_PROPS = "dense size=sm"
CSS_NODE_ROW_CLASSES = "items-center gap-2 flex-nowrap"
CSS_SECTION_GAP = "w-3"

# Modal cards: shared width/layout; scroll variants add max height.
CSS_DIALOG_CARD = "w-full !max-w-5xl"
CSS_DIALOG_SCROLL_AREA = "w-full !max-h-96"

CSS_DEPTH_BG = [
    "bg-white/[3%]",
    "bg-white/[6%]",
    "bg-white/[9%]",
    "bg-white/[12%]",
    "bg-white/[15%]",
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _open_directory(path: Path) -> None:
    """Open a directory in the platform's file manager."""
    p = str(path)
    system = platform.system()
    if system == "Windows":
        os.startfile(p)  # ty: ignore[unresolved-attribute, unused-ignore-comment]
    elif system == "Darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def _depth_class(depth: int) -> str:
    return CSS_DEPTH_BG[min(depth, len(CSS_DEPTH_BG) - 1)]


def _tree_btn(label: str, icon: str, *, on_click, color: str = "primary"):
    """Create a consistently-styled tree-row action button."""
    return (
        ui.button("", icon=icon, color=color, on_click=on_click)
        .props(CSS_TREE_BTN_PROPS)
        .on("click.stop", lambda: None)
    )


# ---------------------------------------------------------------------------
# Node widgets (pure helpers)
# ---------------------------------------------------------------------------


def _stat_badges(node: DarkroomNode) -> None:
    ui.badge(f"{node.stats.image_count} img", color="blue-4").props("outline")
    ui.badge(f"{node.stats.video_count} vid", color="teal-4").props("outline")
    ui.badge(f"{node.stats.other_file_count} other", color="grey-6").props("outline")


def _present_action_details(
    result: ActionResult,
    *,
    after_close: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Show details dialog. If *after_close* is set, it runs after OK (e.g. rescan)."""
    if not result.details:
        return
    with ui.dialog() as dialog, ui.card().classes(CSS_DIALOG_CARD):
        title = "Details" if result.success else "Error"
        ui.label(title).classes("text-lg font-bold")
        ui.label(result.message).classes("text-base font-bold")
        with ui.scroll_area().classes(CSS_DIALOG_SCROLL_AREA):
            ui.label(result.details).classes(
                "font-mono text-xs whitespace-pre-wrap break-all w-full"
            )
        with ui.row().classes("w-full justify-end"):

            async def on_ok() -> None:
                dialog.close()
                if after_close is not None:
                    await after_close()

            ui.button("OK", on_click=on_ok).props("color=primary")
    dialog.open()


# ---------------------------------------------------------------------------
# Main UI (per-connection state + refreshable tree)
# ---------------------------------------------------------------------------


class DarkroomUI:
    """Encapsulates darkroom model, tree expansion state, and NiceGUI refresh."""

    def __init__(self, manager: DarkroomManager) -> None:
        self.manager = manager
        self._all_expansions: dict[str, ui.expansion] = {}
        self._expanded_paths: set[str] = set()

    async def rescan_and_refresh(self) -> None:
        """Rescan disk on a worker thread, then refresh the tree UI.

        Call ``render_tree()`` once first so the NiceGUI refreshable slot exists.
        """
        ui.notify("Scanning darkroom...", type="info", timeout=2000)
        await run.io_bound(self.manager.rescan)
        self.render_tree.refresh()
        ui.notify("Scan complete", type="positive")

    async def _handle_execute_result(self, result: ExecutionResult) -> None:
        if result.success:
            ui.notify(result.message, type="positive")
        else:
            ui.notify(result.message, type="negative", timeout=5000)
        if result.details:
            _present_action_details(
                result,
                after_close=lambda: self.rescan_and_refresh(),
            )
        else:
            await self.rescan_and_refresh()

    async def run_action(self, action: Action, label: str) -> None:
        ui.notify(label + "...", type="info", timeout=2000)
        prep = await run.io_bound(action.prepare)

        if isinstance(prep, PrepareError):
            ui.notify(prep.message, type="negative", timeout=5000)
            if prep.details:
                _present_action_details(prep, after_close=None)
            return

        if prep is None:
            result = await run.io_bound(action.execute, None)
            await self._handle_execute_result(result)
            return

        plan = prep
        if not isinstance(plan, ActionPlan):
            raise AssertionError(f"Unhandled plan type: {type(plan)!r}")

        with ui.dialog() as dialog, ui.card().classes(CSS_DIALOG_CARD):
            ui.label("Review action").classes("text-lg font-bold")
            with ui.scroll_area().classes(CSS_DIALOG_SCROLL_AREA):
                ui.label(plan.preview_text()).classes(
                    "font-mono text-xs whitespace-pre-wrap break-all w-full"
                )
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                async def on_confirm() -> None:
                    dialog.close()
                    result = await run.io_bound(action.execute, plan)
                    await self._handle_execute_result(result)

                ui.button("Confirm", on_click=on_confirm).props("color=primary")
        dialog.open()

    def _show_rename_dialog(self, node: DarkroomNode) -> None:
        async def do_rename():
            new_name = name_input.value.strip()
            if not new_name or new_name == node.name:
                dialog.close()
                return
            dialog.close()
            await self.run_action(
                self.manager.rename_action(node.path, new_name),
                f"Renaming {node.name}",
            )

        with ui.dialog() as dialog, ui.card().classes(CSS_DIALOG_CARD):
            ui.label("Rename Album").classes("text-lg font-bold")
            name_input = ui.input("Album name", value=node.name).classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Rename", on_click=do_rename).props("color=primary")
        dialog.open()

    def _show_new_album_dialog(self) -> None:
        now = datetime.now()

        async def do_create():
            y = year_input.value.strip()
            m = month_input.value.strip()
            d = day_input.value.strip() or None
            n = name_input.value.strip() or None
            dialog.close()
            await self.run_action(
                self.manager.new_album_action(y, m, d, n),
                "Creating album",
            )

        with ui.dialog() as dialog, ui.card().classes(CSS_DIALOG_CARD):
            ui.label("New Album").classes("text-lg font-bold")
            year_input = ui.input("Year", value=str(now.year)).classes("w-full")
            month_input = ui.input("Month", value=f"{now.month:02d}").classes("w-full")
            day_input = ui.input("Day (optional)").classes("w-full")
            name_input = ui.input("Name (optional)").classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Create", on_click=do_create).props("color=primary")
        dialog.open()

    def _action_buttons(self, node: DarkroomNode) -> None:
        # Darkroom section
        ui.icon("camera_roll", size="sm").classes("text-grey-7")
        _tree_btn(
            "Open",
            "folder_open",
            on_click=lambda _n=node: _open_directory(_n.path),
        ).tooltip(
            "Open in file manager"
            if (is_dir := node.path.is_dir())
            else "Folder does not exist on disk"
        ).set_enabled(is_dir)

        if node.node_type == "year":
            return
        if node.name == PUBLISH_FOLDER:
            return

        if node.node_type == "album":
            _tree_btn(
                "Rename",
                "edit",
                on_click=lambda _n=node: self._show_rename_dialog(_n),
            ).tooltip("Rename album")

        if node.node_type in ("album", "subfolder"):
            tidy_color = "red" if "untidy" in node.issues else "primary"
            _tree_btn(
                "Tidy",
                "cleaning_services",
                color=tidy_color,
                on_click=lambda _n=node: self.run_action(
                    self.manager.tidy_action(_n.path),
                    f"Tidying {_n.name}",
                ),
            ).tooltip("Tidy folder")

            settings = self.manager.settings
            if settings.cull_command:
                cull_cmd = settings.cull_command
                _tree_btn(
                    "Cull",
                    "star_rate",
                    on_click=lambda _n=node, cmd=cull_cmd: self.run_action(
                        self.manager.open_external_app_action(cmd, _n.path),
                        f"Culling {_n.name}",
                    ),
                ).tooltip(f"Open in culling app\nCommand: {cull_cmd}")
            if settings.edit_command:
                edit_cmd = settings.edit_command
                _tree_btn(
                    "Edit",
                    "tune",
                    on_click=lambda _n=node, cmd=edit_cmd: self.run_action(
                        self.manager.open_external_app_action(cmd, _n.path),
                        f"Editing {_n.name}",
                    ),
                ).tooltip(f"Open in editing app\nCommand: {edit_cmd}")

        if node.node_type == "album":
            _tree_btn(
                "Publish",
                "publish",
                on_click=lambda _n=node: self.run_action(
                    self.manager.publish_action(_n.path),
                    f"Publishing {_n.name}",
                ),
            ).tooltip("Publish album")

        if node.node_type in ("album", "subfolder"):
            _tree_btn(
                "Archive",
                "archive",
                on_click=lambda _n=node: self.run_action(
                    self.manager.archive_action(_n.path),
                    f"Archiving {_n.name}",
                ),
            ).tooltip("Archive folder")

        # Showroom section
        ui.splitter()
        ui.icon("photo_library", size="sm").classes("text-grey-7")
        showroom_target = self.manager.showroom_path(darkroom_path=node.path)
        _tree_btn(
            "Open",
            "folder_open",
            on_click=lambda _p=showroom_target: _open_directory(_p),
        ).tooltip(
            "Open in file manager"
            if (is_dir := showroom_target.is_dir())
            else "Showroom folder does not exist yet"
        ).set_enabled(is_dir)

        # Archive section
        ui.splitter()
        ui.icon("archive", size="sm").classes("text-grey-7")
        archive_target = self.manager.archive_path(darkroom_path=node.path)
        _tree_btn(
            "Open",
            "folder_open",
            on_click=lambda _p=archive_target: _open_directory(_p),
        ).tooltip(
            "Open in file manager"
            if (is_dir := archive_target.is_dir())
            else "Archive folder does not exist yet"
        ).set_enabled(is_dir)

    def _render_node(self, node: DarkroomNode, depth: int = 0) -> None:
        has_children = bool(node.children)
        icon = "folder" if node.node_type == "root" else "folder"
        bg = _depth_class(depth)

        if has_children:
            path_key = str(node.path)
            exp = (
                ui.expansion(value=path_key in self._expanded_paths)
                .classes(f"w-full {bg}")
                .props("dense")
            )
            self._all_expansions[path_key] = exp

            def _on_toggle(e, key=path_key):
                if e.value:
                    self._expanded_paths.add(key)
                else:
                    self._expanded_paths.discard(key)

            exp.on_value_change(_on_toggle)

            with (
                exp.add_slot("header"),
                ui.row().classes(CSS_NODE_ROW_CLASSES + "  py-2"),
            ):
                ui.icon(icon, size="sm").classes("text-grey-7")
                ui.label(node.name).classes("font-medium")
                ui.element("div").classes(CSS_SECTION_GAP)
                _stat_badges(node)
                ui.element("div").classes(CSS_SECTION_GAP)
                self._action_buttons(node)

            with exp:
                for child in node.children:
                    self._render_node(child, depth + 1)
        else:
            with (
                ui.element("div").classes(f"w-full py-2 pl-4 {bg}"),
                ui.row().classes(CSS_NODE_ROW_CLASSES),
            ):
                ui.icon(icon, size="sm").classes("text-grey-7")
                ui.label(node.name).classes("font-medium")
                ui.element("div").classes(CSS_SECTION_GAP)
                _stat_badges(node)
                ui.element("div").classes(CSS_SECTION_GAP)
                self._action_buttons(node)

    @ui.refreshable_method
    def render_tree(self) -> None:
        self._all_expansions.clear()
        if self.manager.tree is None:
            return
        for year_node in self.manager.tree.children:
            self._render_node(year_node)

    def expand_all(self) -> None:
        for key, exp in self._all_expansions.items():
            exp.open()
            self._expanded_paths.add(key)

    def collapse_all(self) -> None:
        for exp in self._all_expansions.values():
            exp.close()
        self._expanded_paths.clear()

    async def build(self) -> None:
        ui.dark_mode(True)

        with ui.header().classes("items-center px-4 gap-4"):
            ui.label("Photo Darkroom Manager").classes("text-xl font-bold")
            ui.button(
                icon="settings",
                on_click=lambda: ui.navigate.to("/settings"),
            ).props("dense").tooltip("Settings")
            ui.space()
            ui.button(icon="unfold_more", on_click=self.expand_all).props(
                "dense"
            ).tooltip("Expand All")
            ui.button(icon="unfold_less", on_click=self.collapse_all).props(
                "dense"
            ).tooltip("Collapse All")
            ui.button(
                "New Album",
                icon="add",
                on_click=self._show_new_album_dialog,
            ).props("dense")
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=self.rescan_and_refresh,
            ).props("dense")

        with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-0"):
            self.render_tree()

        # Defer first rescan: awaiting it inside build() can race client teardown;
        # ui.timer waits for client.connected() then runs after layout is mounted.
        ui.timer(0.0, self.rescan_and_refresh, once=True)
