"""Contract: actions check their own library roots at prepare and execute.

The engine refuses work early when not ready, but a root can disappear
between that check and the action (e.g. an unplugged drive), so each action
checks the roots it touches itself and refuses without changing files.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    Action,
    ActionPlan,
    ArchiveAction,
    NewBatchAction,
    PrepareError,
    PublishAction,
    RenameAction,
)

ARCHIVE_BASIC = Path("Camera/2026/2026-03 archive basic success")
PUBLISH_BASIC = Path("Camera/2026/2026-03 publish basic success")

Build = Callable[[object], Action]

CASES: dict[str, tuple[str, Build]] = {
    "archive/darkroom": (
        "darkroom",
        lambda s: ArchiveAction(
            s.roots.darkroom / ARCHIVE_BASIC,
            darkroom=s.roots.darkroom,
            archive=s.roots.archive,
        ),
    ),
    "archive/archive": (
        "archive",
        lambda s: ArchiveAction(
            s.roots.darkroom / ARCHIVE_BASIC,
            darkroom=s.roots.darkroom,
            archive=s.roots.archive,
        ),
    ),
    "publish/showroom": (
        "showroom",
        lambda s: PublishAction(
            s.roots.darkroom / PUBLISH_BASIC,
            darkroom=s.roots.darkroom,
            showroom=s.roots.showroom,
        ),
    ),
    "new_batch/darkroom": (
        "darkroom",
        lambda s: NewBatchAction(s.roots.darkroom, "Camera", "2027", "01", None, None),
    ),
    "rename/darkroom": (
        "darkroom",
        lambda s: RenameAction(
            s.roots.darkroom / ARCHIVE_BASIC, s.roots.darkroom, "2026", "04", None, None
        ),
    ),
}


def _unplug(root: Path) -> Path:
    """Move *root* away; return where it went so the test can check it."""
    return Path(shutil.move(root, root.with_name(root.name + "-unplugged")))


@pytest.mark.parametrize("case", CASES)
def test_prepare_refuses_missing_root(photo_setup, case: str) -> None:
    area, build = CASES[case]
    action = build(photo_setup)
    _unplug(getattr(photo_setup.roots, area))
    out = action.prepare()
    assert isinstance(out, PrepareError)
    assert area.capitalize() in out.message


@pytest.mark.parametrize("case", CASES)
def test_execute_refuses_root_lost_after_prepare(photo_setup, case: str) -> None:
    area, build = CASES[case]
    action = build(photo_setup)
    plan = action.prepare()
    assert plan is None or isinstance(plan, ActionPlan)
    moved = _unplug(getattr(photo_setup.roots, area))
    before = sorted(p.relative_to(moved) for p in moved.rglob("*"))

    result = action.execute(plan)

    assert not result.success
    assert area.capitalize() in result.message
    assert sorted(p.relative_to(moved) for p in moved.rglob("*")) == before
