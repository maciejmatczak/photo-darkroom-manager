"""NiceGUI layout: controller/page shell, action orchestration, tree root."""

from __future__ import annotations

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
from photo_darkroom_manager.gui.node import DarkroomNodeUI
from photo_darkroom_manager.gui.widgets import (
    CSS_DIALOG_CARD,
    CSS_DIALOG_SCROLL_AREA,
)
from photo_darkroom_manager.manager import DarkroomManager
from photo_darkroom_manager.scan import DarkroomNode


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


class DarkroomUI:
    """Controller and page shell: owns the manager, registry, and action dispatch."""

    def __init__(self, manager: DarkroomManager) -> None:
        self.manager = manager
        self.registry: dict[Path, DarkroomNodeUI] = {}
        self.expanded_paths: set[str] = set()

    def register(self, path: Path, node_ui: DarkroomNodeUI) -> None:
        """Called by each DarkroomNodeUI on render to add itself to the registry."""
        self.registry[path] = node_ui

    # ------------------------------------------------------------------
    # Rescan: full tree (first load / manual refresh)
    # ------------------------------------------------------------------

    async def rescan_and_refresh(self) -> None:
        """Rescan disk on a worker thread, then refresh the tree UI.

        Call ``render_tree()`` once first so the NiceGUI refreshable slot exists.
        """
        ui.notify("Scanning darkroom...", type="info", timeout=2000)
        await run.io_bound(self.manager.rescan)
        self.registry.clear()
        self.render_tree.refresh()
        ui.notify("Scan complete", type="positive")

    # ------------------------------------------------------------------
    # Rescan: scoped (after an action)
    # ------------------------------------------------------------------

    async def _refresh_scoped(self, rescan_path: Path) -> None:
        """Rescan the subtree at *rescan_path* and refresh only the affected zones.

        Looks up *rescan_path* in the registry; on a miss (e.g. new year folder)
        walks parent paths until a registered ancestor is found.  Falls back to a
        full rescan if no ancestor is registered either.
        """
        # Resolve to the nearest registered node.
        target_ui: DarkroomNodeUI | None = None
        candidate = rescan_path
        while True:
            target_ui = self.registry.get(candidate)
            if target_ui is not None:
                break
            parent = candidate.parent
            if parent == candidate:
                # Reached filesystem root without a registry hit.
                break
            candidate = parent

        if target_ui is None:
            # Fallback: full rescan.
            await self.rescan_and_refresh()
            return

        # Run the local disk scan off the UI thread.
        await run.io_bound(self.manager.rescan_subtree, target_ui.node)

        # Refresh the two zones of the target node.
        target_ui.refresh_children()
        target_ui.refresh_header()

        # Walk ancestors, refreshing their header zone only (stats/issue badges).
        ancestor: DarkroomNode | None = target_ui.node.parent
        while ancestor is not None:
            ancestor_ui = self.registry.get(ancestor.path)
            if ancestor_ui is not None:
                ancestor_ui.refresh_header()
            ancestor = ancestor.parent

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    async def _handle_execute_result(self, result: ExecutionResult) -> None:
        if result.success:
            ui.notify(result.message, type="positive")
        else:
            ui.notify(result.message, type="negative", timeout=5000)

        if result.rescan_node_path is not None:
            rescan_path = result.rescan_node_path
            if result.details:
                # Show details first; rescan runs after the user dismisses the dialog.
                _present_action_details(
                    result,
                    after_close=lambda _p=rescan_path: self._refresh_scoped(_p),
                )
            else:
                await self._refresh_scoped(rescan_path)
        elif result.details:
            _present_action_details(result, after_close=None)

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

    # ------------------------------------------------------------------
    # New-album dialog (controller-level: not node-scoped)
    # ------------------------------------------------------------------

    def _show_new_album_dialog(self) -> None:
        now = datetime.now()

        async def do_create() -> None:
            pair = _required_year_month_str(year_input.value, month_input.value)
            if pair is None:
                ui.notify("Year and month are required", type="negative", timeout=5000)
                return
            y, m = pair
            d = _optional_number_to_day_str(day_input.value)
            n = name_input.value.strip() or None
            dialog.close()
            await self.run_action(
                self.manager.new_album_action(y, m, d, n),
                "Creating album",
            )

        with ui.dialog() as dialog, ui.card().classes(CSS_DIALOG_CARD):
            ui.label("New Album").classes("text-lg font-bold")
            year_input = ui.number(
                "Year",
                value=float(now.year),
                precision=0,
                min=1000,
                max=9999,
            ).classes("w-full")
            month_input = ui.number(
                "Month",
                value=float(now.month),
                precision=0,
                min=1,
                max=12,
            ).classes("w-full")
            day_input = ui.number(
                "Day (optional)",
                value=None,
                precision=0,
                min=1,
                max=31,
            ).classes("w-full")
            name_input = ui.input("Name (optional)").classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Create", on_click=do_create).props("color=primary")
        dialog.open()

    # ------------------------------------------------------------------
    # Tree: expand / collapse helpers
    # ------------------------------------------------------------------

    def expand_all(self) -> None:
        for path, node_ui in self.registry.items():
            node_ui.set_expanded(True)
            self.expanded_paths.add(str(path))

    def collapse_all(self) -> None:
        for node_ui in self.registry.values():
            node_ui.set_expanded(False)
        self.expanded_paths.clear()

    # ------------------------------------------------------------------
    # Tree root (refreshable -- full rebuild on full rescan only)
    # ------------------------------------------------------------------

    @ui.refreshable_method
    def render_tree(self) -> None:
        self.registry.clear()
        if self.manager.tree is None:
            return
        for year_node in self.manager.tree.children:
            year_ui = DarkroomNodeUI(year_node, self, depth=0)
            year_ui.render()

    # ------------------------------------------------------------------
    # Page builder
    # ------------------------------------------------------------------

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
