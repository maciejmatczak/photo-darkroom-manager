"""Contract: actions check their own library roots when they prepare.

The engine refuses work early when not ready, but a root can disappear
between that check and the action (e.g. an unplugged drive), so each action
checks the roots it touches itself and refuses without changing files. The
engine prepares again before running a plan, so a root lost after the
preview is refused the same way.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionRefusedError,
    archive,
    new_batch,
    publish,
    rename,
)

ARCHIVE_BASIC = Path("Camera/2026/2026-03 archive basic success")
PUBLISH_BASIC = Path("Camera/2026/2026-03 publish basic success")

Prepare = Callable[[object], object]

CASES: dict[str, tuple[str, Prepare]] = {
    "archive/darkroom": (
        "darkroom",
        lambda s: archive.prepare(
            s.roots.darkroom / ARCHIVE_BASIC, s.roots.darkroom, s.roots.archive
        ),
    ),
    "archive/archive": (
        "archive",
        lambda s: archive.prepare(
            s.roots.darkroom / ARCHIVE_BASIC, s.roots.darkroom, s.roots.archive
        ),
    ),
    "publish/showroom": (
        "showroom",
        lambda s: publish.prepare(
            s.roots.darkroom / PUBLISH_BASIC, s.roots.darkroom, s.roots.showroom
        ),
    ),
    "new_batch/darkroom": (
        "darkroom",
        lambda s: new_batch.prepare(s.roots.darkroom, "Camera", date="2027-01"),
    ),
    "rename/darkroom": (
        "darkroom",
        lambda s: rename.prepare(
            s.roots.darkroom / ARCHIVE_BASIC, s.roots.darkroom, date="2026-04"
        ),
    ),
}


def _unplug(root: Path) -> Path:
    """Move *root* away; return where it went so the test can check it."""
    return Path(shutil.move(root, root.with_name(root.name + "-unplugged")))


@pytest.mark.parametrize("case", CASES)
def test_preparing_refuses_a_missing_root(photo_setup, case: str) -> None:
    area, prepare = CASES[case]
    prepare(photo_setup)
    moved = _unplug(getattr(photo_setup.roots, area))
    before = sorted(p.relative_to(moved) for p in moved.rglob("*"))
    with pytest.raises(ActionRefusedError, match=area.capitalize()):
        prepare(photo_setup)
    assert sorted(p.relative_to(moved) for p in moved.rglob("*")) == before
