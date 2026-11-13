"""Contract: file actions never lose user files and report what changed.

Each test prepares and executes an action through the engine, then
compares the whole workspace (darkroom, showroom and archive) before and
after.
"""

import hashlib
from collections import Counter
from pathlib import Path

import pytest
from conftest import run_planned

from photo_darkroom_manager.core.engine import ActionRefusedError, Engine
from photo_darkroom_manager.core.library import PHOTOS_FOLDER

BATCHES = Path("Camera") / "2026"
TIDY_BASIC = BATCHES / "2026-03 tidy basic moves jpg and xmp"
ARCHIVE_BASIC = BATCHES / "2026-03 archive basic success"
ARCHIVE_CONFLICT = BATCHES / "2026-03 archive will fail on conflict"
PUBLISH_BASIC = BATCHES / "2026-03 publish basic success"


def _id(relative: Path) -> str:
    return relative.as_posix()


def _roots(manager: Engine) -> list[Path]:
    roots = [manager.darkroom, manager.showroom, manager.archive]
    assert all(r is not None for r in roots)
    return [r for r in roots if r is not None]


def _contents(manager: Engine) -> Counter[tuple[str, str]]:
    """Multiset of (file name, content hash) across all three roots."""
    out: Counter[tuple[str, str]] = Counter()
    for root in _roots(manager):
        for p in root.rglob("*"):
            if p.is_file():
                out[(p.name, hashlib.sha256(p.read_bytes()).hexdigest())] += 1
    return out


def _snapshot(manager: Engine) -> dict[Path, bytes]:
    """Exact layout: every file path and its bytes, across all three roots."""
    return {
        p: p.read_bytes()
        for root in _roots(manager)
        for p in root.rglob("*")
        if p.is_file()
    }


def _ok(manager: Engine, name: str, relative: Path) -> None:
    done = run_planned(manager, name, _id(relative))
    assert done.result.outcome == "ok", done


def test_tidy_keeps_every_file(photo_setup) -> None:
    mgr = photo_setup.engine
    photo_setup.darkroom_has_dir(TIDY_BASIC)
    before = _contents(mgr)
    _ok(mgr, "tidy", TIDY_BASIC)
    assert _contents(mgr) == before


def test_archive_keeps_every_file(photo_setup) -> None:
    mgr = photo_setup.engine
    photo_setup.darkroom_has_dir(ARCHIVE_BASIC)
    before = _contents(mgr)
    _ok(mgr, "archive", ARCHIVE_BASIC)
    assert _contents(mgr) == before


def test_publish_keeps_every_file(photo_setup) -> None:
    mgr = photo_setup.engine
    photo_setup.darkroom_has_dir(PUBLISH_BASIC)
    before = _contents(mgr)
    _ok(mgr, "publish", PUBLISH_BASIC)
    assert _contents(mgr) == before


def test_archive_subfolder_leaves_rest_of_batch(photo_setup) -> None:
    mgr = photo_setup.engine
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BASIC)
    photos = batch / PHOTOS_FOLDER
    others = {p for p in batch.rglob("*") if p.is_file() and photos not in p.parents}
    assert others
    _ok(mgr, "archive", ARCHIVE_BASIC / PHOTOS_FOLDER)
    assert not photos.exists() or not any(photos.rglob("*.*"))
    assert all(p.is_file() for p in others)


def test_conflicts_without_an_answer_leave_disk_unchanged(photo_setup) -> None:
    mgr = photo_setup.engine
    photo_setup.darkroom_has_dir(ARCHIVE_CONFLICT)
    before = _snapshot(mgr)
    plan = mgr.action_prepare_archive(_id(ARCHIVE_CONFLICT))
    assert plan.conflicts
    with pytest.raises(ActionRefusedError):
        mgr.action_archive(plan)
    assert _snapshot(mgr) == before


def test_tree_changing_actions_report_what_to_refresh(photo_setup) -> None:
    """Each successful file action rescans a node covering its change."""
    mgr = photo_setup.engine
    mgr.library_scan()
    cases = [
        ("tidy", TIDY_BASIC),
        ("archive", ARCHIVE_BASIC),
        ("publish", PUBLISH_BASIC),
    ]
    for name, rel in cases:
        photo_setup.darkroom_has_dir(rel)
        done = run_planned(mgr, name, _id(rel))
        assert done.result.outcome == "ok", rel
        refreshed = done.library_refreshed
        assert refreshed is not None, rel
        assert _id(rel) == refreshed or _id(rel).startswith(f"{refreshed}/"), rel
