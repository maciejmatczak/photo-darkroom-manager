"""DarkroomNodeUI -- per-node view-controller binding two independent refresh zones."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui
from pydantic import ValidationError

from photo_darkroom_manager.gui.widgets import (
    CSS_DIALOG_CARD,
    CSS_NODE_ROW_CLASSES,
    CSS_SECTION_GAP,
    depth_class,
    open_directory,
    stat_badges,
    tree_btn,
)
from photo_darkroom_manager.models import AlbumFolderName, format_validation_error
from photo_darkroom_manager.scan import DarkroomNode
from photo_darkroom_manager.settings import PUBLISH_FOLDER

if TYPE_CHECKING:
    from photo_darkroom_manager.gui.layout import DarkroomUI


def _optional_number_to_day_str(v: float | None) -> str | None:
    if v is None:
        return None
    return str(int(v))


def _required_year_month_str(
    y: float | None, m: float | None
) -> tuple[str, str] | None:
    if y is None or m is None:
        return None
    return str(int(y)), str(int(m))


class DarkroomNodeUI:
    """Renders one DarkroomNode with two independent refreshable zones.

    Header zone: folder name, stat badges, action buttons.
    Children zone: the list of child DarkroomNodeUI instances.

    Both zones are always registered in ``render()`` (even for leaf nodes that
    currently have no children) so ``refresh_header()`` and
    ``refresh_children()`` always work.  If a leaf node gains children after a
    scoped rescan, the children appear inside the existing container without an
    expand toggle.  A full manual Refresh rebuilds the proper expansion widget.
    """

    def __init__(
        self,
        node: DarkroomNode,
        controller: DarkroomUI,
        depth: int = 0,
    ) -> None:
        self.node = node
        self._controller = controller
        self._depth = depth
        self._expansion: ui.expansion | None = None

    # ------------------------------------------------------------------
    # Refresh zones (public API for the controller)
    # ------------------------------------------------------------------

    def refresh_header(self) -> None:
        self._render_header.refresh()

    def refresh_children(self) -> None:
        self._render_children.refresh()

    def set_expanded(self, value: bool) -> None:
        """Open or close the expansion widget if this node has one."""
        if self._expansion is not None:
            if value:
                self._expansion.open()
            else:
                self._expansion.close()

    # ------------------------------------------------------------------
    # Outer shell
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Build the outer container and wire both refresh zones.

        Registers ``self`` in the controller's registry keyed by ``node.path``.
        """
        self._controller.register(self.node.path, self)
        bg = depth_class(self._depth)

        if self.node.children:
            path_key = str(self.node.path)
            is_expanded = path_key in self._controller.expanded_paths
            exp = ui.expansion(value=is_expanded).classes(f"w-full {bg}").props("dense")
            self._expansion = exp

            def _on_toggle(e, key=path_key) -> None:
                if e.value:
                    self._controller.expanded_paths.add(key)
                else:
                    self._controller.expanded_paths.discard(key)

            exp.on_value_change(_on_toggle)

            with (
                exp.add_slot("header"),
                ui.row().classes(CSS_NODE_ROW_CLASSES + "  py-2"),
            ):
                self._render_header()

            with exp:
                self._render_children()
        else:
            with ui.element("div").classes(f"w-full py-2 pl-4 {bg}"):
                with ui.row().classes(CSS_NODE_ROW_CLASSES):
                    self._render_header()
                # Always wire children zone even for leaves so refresh_children()
                # is always available; see class docstring.
                self._render_children()

    # ------------------------------------------------------------------
    # Header zone
    # ------------------------------------------------------------------

    @ui.refreshable_method
    def _render_header(self) -> None:
        node = self.node
        ui.icon("folder", size="sm").classes("text-grey-7")
        ui.label(node.name).classes("font-medium")
        ui.element("div").classes(CSS_SECTION_GAP)
        stat_badges(node)
        ui.element("div").classes(CSS_SECTION_GAP)
        self._action_buttons()

    def _action_buttons(self) -> None:
        node = self.node
        mgr = self._controller.manager
        settings = mgr.settings

        # Darkroom section
        ui.icon("camera_roll", size="sm").classes("text-grey-7")
        tree_btn(
            "Open",
            "folder_open",
            on_click=lambda _p=node.path: open_directory(_p),
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
            tree_btn(
                "Rename",
                "edit",
                on_click=lambda: self._show_rename_dialog(),
            ).tooltip("Rename album")

        if node.node_type in ("album", "subfolder"):
            tidy_color = "red" if "untidy" in node.issues else "primary"
            tree_btn(
                "Tidy",
                "cleaning_services",
                color=tidy_color,
                on_click=lambda: self._controller.run_action(
                    mgr.tidy_action(node.path),
                    f"Tidying {node.name}",
                ),
            ).tooltip("Tidy folder")

            if settings.cull_command:
                cull_cmd = settings.cull_command
                tree_btn(
                    "Cull",
                    "star_rate",
                    on_click=lambda cmd=cull_cmd: self._controller.run_action(
                        mgr.open_external_app_action(cmd, node.path),
                        f"Culling {node.name}",
                    ),
                ).tooltip(f"Open in culling app\nCommand: {cull_cmd}")

            if settings.edit_command:
                edit_cmd = settings.edit_command
                tree_btn(
                    "Edit",
                    "tune",
                    on_click=lambda cmd=edit_cmd: self._controller.run_action(
                        mgr.open_external_app_action(cmd, node.path),
                        f"Editing {node.name}",
                    ),
                ).tooltip(f"Open in editing app\nCommand: {edit_cmd}")

        if node.node_type == "album":
            tree_btn(
                "Publish",
                "publish",
                on_click=lambda: self._controller.run_action(
                    mgr.publish_action(node.path),
                    f"Publishing {node.name}",
                ),
            ).tooltip("Publish album")

        if node.node_type in ("album", "subfolder"):
            tree_btn(
                "Archive",
                "archive",
                on_click=lambda: self._controller.run_action(
                    mgr.archive_action(node.path),
                    f"Archiving {node.name}",
                ),
            ).tooltip("Archive folder")

        # Showroom section
        ui.splitter()
        ui.icon("photo_library", size="sm").classes("text-grey-7")
        showroom_target = mgr.showroom_path(darkroom_path=node.path)
        tree_btn(
            "Open",
            "folder_open",
            on_click=lambda _p=showroom_target: open_directory(_p),
        ).tooltip(
            "Open in file manager"
            if (is_dir := showroom_target.is_dir())
            else "Showroom folder does not exist yet"
        ).set_enabled(is_dir)

        # Archive section
        ui.splitter()
        ui.icon("archive", size="sm").classes("text-grey-7")
        archive_target = mgr.archive_path(darkroom_path=node.path)
        tree_btn(
            "Open",
            "folder_open",
            on_click=lambda _p=archive_target: open_directory(_p),
        ).tooltip(
            "Open in file manager"
            if (is_dir := archive_target.is_dir())
            else "Archive folder does not exist yet"
        ).set_enabled(is_dir)

    # ------------------------------------------------------------------
    # Rename dialog (node-scoped)
    # ------------------------------------------------------------------

    def _show_rename_dialog(self) -> None:
        node = self.node
        try:
            parsed = AlbumFolderName.from_str(node.name)
        except ValidationError:
            parsed = None

        try:
            year_default = int(node.path.parent.name)
        except ValueError:
            year_default = datetime.now().year

        async def do_rename() -> None:
            pair = _required_year_month_str(year_input.value, month_input.value)
            if pair is None:
                ui.notify("Year and month are required", type="negative", timeout=5000)
                return
            y, m = pair
            d = _optional_number_to_day_str(day_input.value)
            n = name_input.value.strip() or None
            try:
                folder_name = AlbumFolderName(
                    year=y, month=m, day=d, name=n
                ).folder_name
            except ValidationError as e:
                ui.notify(
                    format_validation_error(e),
                    type="negative",
                    timeout=5000,
                )
                return
            if folder_name == node.name:
                dialog.close()
                return
            dialog.close()
            await self._controller.run_action(
                self._controller.manager.rename_action(node.path, y, m, d, n),
                f"Renaming {node.name}",
            )

        with ui.dialog() as dialog, ui.card().classes(CSS_DIALOG_CARD):
            ui.label("Rename Album").classes("text-lg font-bold")
            if parsed is None:
                ui.label(
                    "Current name could not be parsed — fill fields manually."
                ).classes("text-sm text-grey-7")

            year_input = ui.number(
                "Year",
                value=float(year_default),
                precision=0,
                min=1000,
                max=9999,
            ).classes("w-full")
            year_input.props("readonly")

            month_val = int(parsed.month) if parsed else None
            day_val = int(parsed.day) if parsed and parsed.day else None

            month_input = ui.number(
                "Month",
                value=float(month_val) if month_val is not None else None,
                precision=0,
                min=1,
                max=12,
            ).classes("w-full")
            day_input = ui.number(
                "Day (optional)",
                value=float(day_val) if day_val is not None else None,
                precision=0,
                min=1,
                max=31,
            ).classes("w-full")
            name_input = ui.input(
                "Name (optional)",
                value=parsed.name if parsed and parsed.name else "",
            ).classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Rename", on_click=do_rename).props("color=primary")
        dialog.open()

    # ------------------------------------------------------------------
    # Children zone
    # ------------------------------------------------------------------

    @ui.refreshable_method
    def _render_children(self) -> None:
        for child in self.node.children:
            child_ui = DarkroomNodeUI(child, self._controller, self._depth + 1)
            child_ui.render()

    # ------------------------------------------------------------------
    # Path-based lookup helper
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self.node.path
