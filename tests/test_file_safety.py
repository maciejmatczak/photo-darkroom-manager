"""Contract: file actions never lose user files and report what changed.

Each test runs an action through the public engine factories,
``prepare()`` and ``engine.action_execute()``, then compares the whole
workspace (darkroom, showroom and archive) before and after.
"""

import hashlib
from collections import Counter
from pathlib import Path

from photo_darkroom_manager.actions import ActionPlan, PrepareError
from photo_darkroom_manager.engine import Engine
from photo_darkroom_manager.library import PHOTOS_FOLDER

BATCHES = Path("Camera") / "2026"
TIDY_BASIC = BATCHES / "2026-03 tidy basic moves jpg and xmp"
ARCHIVE_BASIC = BATCHES / "2026-03 archive basic success"
ARCHIVE_CONFLICT = BATCHES / "2026-03 archive will fail on conflict"
PUBLISH_BASIC = BATCHES / "2026-03 publish basic success"


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


def _run(manager: Engine, action):
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return manager.action_execute(action, plan)


def test_tidy_keeps_every_file(photo_setup) -> None:
    mgr = photo_setup.engine
    batch = photo_setup.darkroom_has_dir(TIDY_BASIC)
    before = _contents(mgr)
    result = _run(mgr, mgr.action_tidy(batch))
    assert result.success
    assert _contents(mgr) == before


def test_archive_keeps_every_file(photo_setup) -> None:
    mgr = photo_setup.engine
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BASIC)
    before = _contents(mgr)
    result = _run(mgr, mgr.action_archive(batch))
    assert result.success
    assert _contents(mgr) == before


def test_publish_keeps_every_file(photo_setup) -> None:
    mgr = photo_setup.engine
    batch = photo_setup.darkroom_has_dir(PUBLISH_BASIC)
    before = _contents(mgr)
    result = _run(mgr, mgr.action_publish(batch))
    assert result.success
    assert _contents(mgr) == before


def test_archive_subfolder_leaves_rest_of_batch(photo_setup) -> None:
    mgr = photo_setup.engine
    batch = photo_setup.darkroom_has_dir(ARCHIVE_BASIC)
    photos = batch / PHOTOS_FOLDER
    others = {p for p in batch.rglob("*") if p.is_file() and photos not in p.parents}
    assert others
    result = _run(mgr, mgr.action_archive(photos))
    assert result.success
    assert not photos.exists() or not any(photos.rglob("*.*"))
    assert all(p.is_file() for p in others)


def test_refused_prepare_leaves_disk_unchanged(photo_setup) -> None:
    mgr = photo_setup.engine
    batch = photo_setup.darkroom_has_dir(ARCHIVE_CONFLICT)
    before = _snapshot(mgr)
    out = mgr.action_archive(batch).prepare()
    assert isinstance(out, PrepareError)
    assert _snapshot(mgr) == before


def test_tree_changing_actions_report_what_to_refresh(photo_setup) -> None:
    """Each successful file action names a darkroom path covering its change."""
    mgr = photo_setup.engine
    darkroom = photo_setup.roots.darkroom
    cases = [
        (mgr.action_tidy, TIDY_BASIC),
        (mgr.action_archive, ARCHIVE_BASIC),
        (mgr.action_publish, PUBLISH_BASIC),
    ]
    for factory, rel in cases:
        target = photo_setup.darkroom_has_dir(rel)
        result = _run(mgr, factory(target))
        assert result.success, rel
        hint = result.rescan_node_path
        assert hint is not None, rel
        assert hint == target or hint in target.parents, rel
        assert hint == darkroom or darkroom in hint.parents, rel
