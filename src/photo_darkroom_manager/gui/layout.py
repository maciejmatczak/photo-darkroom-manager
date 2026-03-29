"""NiceGUI layout: header bar, recursive expansion tree, action buttons."""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from nicegui import run, ui

from photo_darkroom_manager.constants import PUBLISH_FOLDER
from photo_darkroom_manager.gui.model import App
from photo_darkroom_manager.gui.scanner import DarkroomNode

# ---------------------------------------------------------------------------
# Shared style tokens -- single source of truth for recurring props/classes
# ---------------------------------------------------------------------------
TREE_BTN_PROPS = "dense size=sm"
NODE_ROW_CLASSES = "items-center gap-2 flex-nowrap"

_DEPTH_BG = [
    "bg-white/[3%]",
    "bg-white/[6%]",
    "bg-white/[9%]",
    "bg-white/[12%]",
    "bg-white/[15%]",
]

_all_expansions: list[ui.expansion] = []


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _open_directory(path: Path) -> None:
    """Open a directory in the platform's file manager."""
    p = str(path)
    system = platform.system()
    if system == "Windows":
        os.startfile(p)
    elif system == "Darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def _depth_class(depth: int) -> str:
    return _DEPTH_BG[min(depth, len(_DEPTH_BG) - 1)]


def _tree_btn(label: str, icon: str, *, on_click, color: str = "primary"):
    """Create a consistently-styled tree-row action button."""
    return (
        ui.button(label, icon=icon, color=color, on_click=on_click)
        .props(TREE_BTN_PROPS)
        .on("click.stop", lambda: None)
    )


# ---------------------------------------------------------------------------
# Node widgets
# ---------------------------------------------------------------------------


def _stat_badges(node: DarkroomNode) -> None:
    if node.stats.image_count > 0:
        ui.badge(f"{node.stats.image_count} img", color="blue-4").props("outline")
    if node.stats.video_count > 0:
        ui.badge(f"{node.stats.video_count} vid", color="teal-4").props("outline")


def _open_folder_button(node: DarkroomNode) -> None:
    _tree_btn(
        "Open", "folder_open", on_click=lambda _n=node: _open_directory(_n.path)
    ).tooltip("Open in file manager")


def _action_buttons(node: DarkroomNode, model: App, rebuild_fn) -> None:
    if node.node_type == "year":
        return
    if node.name == PUBLISH_FOLDER:
        return

    if node.node_type in ("album", "subfolder"):
        tidy_color = "red" if "untidy" in node.issues else "primary"
        _tree_btn(
            "Tidy",
            "cleaning_services",
            color=tidy_color,
            on_click=lambda _n=node: _run_action(
                model.tidy, _n.path, model, rebuild_fn, f"Tidying {_n.name}"
            ),
        )
        _tree_btn(
            "Archive",
            "archive",
            on_click=lambda _n=node: _run_action(
                model.archive, _n.path, model, rebuild_fn, f"Archiving {_n.name}"
            ),
        )

    if node.node_type == "album":
        _tree_btn(
            "Publish",
            "publish",
            on_click=lambda _n=node: _run_action(
                model.publish, _n.path, model, rebuild_fn, f"Publishing {_n.name}"
            ),
        )
        _tree_btn(
            "Rename",
            "edit",
            on_click=lambda _n=node: _show_rename_dialog(_n, model, rebuild_fn),
        )


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


async def _run_action(action_fn, path: Path, model: App, rebuild_fn, label: str):
    ui.notify(label + "...", type="info", timeout=2000)
    result = await run.io_bound(action_fn, path)
    if result.success:
        ui.notify(result.message, type="positive")
    else:
        ui.notify(result.message, type="negative", timeout=5000)
    await _rescan_and_rebuild(model, rebuild_fn)


async def _rescan_and_rebuild(model: App, rebuild_fn):
    await run.io_bound(model.rescan)
    rebuild_fn()


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


def _show_rename_dialog(node: DarkroomNode, model: App, rebuild_fn):
    async def do_rename():
        new_name = name_input.value.strip()
        if not new_name or new_name == node.name:
            dialog.close()
            return
        result = await run.io_bound(model.rename_album, node.path, new_name)
        dialog.close()
        if result.success:
            ui.notify(result.message, type="positive")
        else:
            ui.notify(result.message, type="negative", timeout=5000)
        await _rescan_and_rebuild(model, rebuild_fn)

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Rename Album").classes("text-lg font-bold")
        name_input = ui.input("Album name", value=node.name).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Rename", on_click=do_rename).props("color=primary")
    dialog.open()


def _show_new_album_dialog(model: App, rebuild_fn):
    now = datetime.now()

    async def do_create():
        y = year_input.value.strip()
        m = month_input.value.strip()
        d = day_input.value.strip() or None
        n = name_input.value.strip()
        result = await run.io_bound(model.new_album, y, m, d, n)
        dialog.close()
        if result.success:
            ui.notify(result.message, type="positive")
        else:
            ui.notify(result.message, type="negative", timeout=5000)
        await _rescan_and_rebuild(model, rebuild_fn)

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("New Album").classes("text-lg font-bold")
        year_input = ui.input("Year", value=str(now.year)).classes("w-full")
        month_input = ui.input("Month", value=f"{now.month:02d}").classes("w-full")
        day_input = ui.input("Day (optional)").classes("w-full")
        name_input = ui.input("Name (optional)").classes("w-full")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Create", on_click=do_create).props("color=primary")
    dialog.open()


# ---------------------------------------------------------------------------
# Tree rendering
# ---------------------------------------------------------------------------


def _render_node(node: DarkroomNode, model: App, rebuild_fn, depth: int = 0) -> None:
    has_children = bool(node.children)
    icon = "folder_open" if node.node_type == "root" else "folder"
    bg = _depth_class(depth)

    if has_children:
        exp = ui.expansion(icon=icon).classes(f"w-full {bg}").props("dense")
        _all_expansions.append(exp)

        with exp.add_slot("header"), ui.row().classes(NODE_ROW_CLASSES):
            ui.label(node.name).classes("font-medium")
            _stat_badges(node)
            _open_folder_button(node)
            _action_buttons(node, model, rebuild_fn)

        with exp:
            for child in node.children:
                _render_node(child, model, rebuild_fn, depth + 1)
    else:
        with ui.row().classes(f"{NODE_ROW_CLASSES} pl-10 py-0.5 w-full {bg}"):
            ui.icon(icon, size="sm").classes("text-grey-7")
            ui.label(node.name).classes("font-medium")
            _stat_badges(node)
            _open_folder_button(node)
            _action_buttons(node, model, rebuild_fn)


# ---------------------------------------------------------------------------
# Top-level UI builder
# ---------------------------------------------------------------------------


def build_ui(model: App) -> None:
    state: dict = {"tree_container": None}

    def rebuild_tree():
        container = state["tree_container"]
        if container is None:
            return
        _all_expansions.clear()
        container.clear()
        if model.tree is None:
            return
        with container:
            for year_node in model.tree.children:
                _render_node(year_node, model, rebuild_tree)

    def expand_all():
        for exp in _all_expansions:
            exp.open()

    def collapse_all():
        for exp in _all_expansions:
            exp.close()

    async def refresh():
        ui.notify("Scanning darkroom...", type="info", timeout=2000)
        await run.io_bound(model.rescan)
        rebuild_tree()
        ui.notify("Scan complete", type="positive")

    ui.dark_mode(True)

    with ui.header().classes("items-center px-4 gap-4"):
        ui.label("Photo Darkroom Manager").classes("text-xl font-bold")
        ui.space()
        ui.button(icon="unfold_more", on_click=expand_all).props("dense").tooltip(
            "Expand All"
        )
        ui.button(icon="unfold_less", on_click=collapse_all).props("dense").tooltip(
            "Collapse All"
        )
        ui.button(
            "New Album",
            icon="add",
            on_click=lambda: _show_new_album_dialog(model, rebuild_tree),
        ).props("dense")
        ui.button("Refresh", icon="refresh", on_click=refresh).props("dense")

    with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-0"):
        state["tree_container"] = ui.element("div").classes("w-full")

    model.rescan()
    rebuild_tree()
