"""Shared UI tokens, helpers, and micro-widgets used across the GUI."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Callable
from pathlib import Path

from nicegui import ui

from photo_darkroom_manager.scan import DarkroomNode

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


def open_directory(path: Path) -> None:
    """Open a directory in the platform's file manager."""
    p = str(path)
    system = platform.system()
    if system == "Windows":
        os.startfile(p)  # ty: ignore[unresolved-attribute, unused-ignore-comment]
    elif system == "Darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def depth_class(depth: int) -> str:
    return CSS_DEPTH_BG[min(depth, len(CSS_DEPTH_BG) - 1)]


def tree_btn(label: str, icon: str, *, on_click: Callable, color: str = "primary"):
    """Create a consistently-styled tree-row action button."""
    return (
        ui.button("", icon=icon, color=color, on_click=on_click)
        .props(CSS_TREE_BTN_PROPS)
        .on("click.stop", lambda: None)
    )


def stat_badges(node: DarkroomNode) -> None:
    ui.badge(f"{node.stats.image_count} img", color="blue-4").props("outline")
    ui.badge(f"{node.stats.video_count} vid", color="teal-4").props("outline")
    ui.badge(f"{node.stats.other_file_count} other", color="grey-6").props("outline")
