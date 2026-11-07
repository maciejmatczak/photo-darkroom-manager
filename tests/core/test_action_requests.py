"""Contract: engine/action-requests scenarios, through the engine."""

import threading
from pathlib import Path

import pytest
from conftest import MakeEngine, Roots

from photo_darkroom_manager.core import actions as actions_module
from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    Launch,
    MakeDir,
    Rename,
    TidyAction,
)
from photo_darkroom_manager.core.engine import (
    ActionNotAllowedError,
    Engine,
    EngineBusyError,
    NodeNotFoundError,
)
from photo_darkroom_manager.core.library import PUBLISH_FOLDER, NodeAction

BATCH = "Camera/2026/2026-10 Walk"


def _batch(roots: Roots, *files: str) -> Path:
    path = roots.darkroom / BATCH
    path.mkdir(parents=True)
    for name in files:
        (path / name).write_bytes(name.encode())
    return path


def _plan(action) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


# ---------------------------------------------------------------------------
# Requests address a node by id
# ---------------------------------------------------------------------------


def test_archive_without_a_scan(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    plan = _plan(engine.action_archive(BATCH))
    assert plan.request.node_id == BATCH
    assert plan.request.action == NodeAction.ARCHIVE
    assert not engine.library_scanned


def test_id_outside_the_library_layout(roots: Roots, engine: Engine) -> None:
    (roots.darkroom / "Camera/notes").mkdir(parents=True)
    with pytest.raises(NodeNotFoundError) as exc:
        engine.action_tidy("Camera/notes")
    assert exc.value.node_id == "Camera/notes"


def test_folder_gone(engine: Engine) -> None:
    with pytest.raises(NodeNotFoundError) as exc:
        engine.action_archive(BATCH)
    assert exc.value.node_id == BATCH


@pytest.mark.internal
@pytest.mark.parametrize("node_id", ["..", "Camera/../x", "/Camera", "C:/x"])
def test_malformed_ids_are_not_found(engine: Engine, node_id: str) -> None:
    with pytest.raises(NodeNotFoundError):
        engine.action_open(node_id)


def test_ids_follow_on_disk_names(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    plan = _plan(engine.action_tidy(BATCH.lower()))
    assert plan.request.node_id == BATCH


# ---------------------------------------------------------------------------
# Actions are guarded by node kind
# ---------------------------------------------------------------------------


def test_archive_a_year(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    with pytest.raises(ActionNotAllowedError) as exc:
        engine.action_archive("Camera/2026")
    assert (exc.value.node_id, exc.value.action, exc.value.kind) == (
        "Camera/2026",
        NodeAction.ARCHIVE,
        "year",
    )
    assert (roots.darkroom / BATCH / "a.jpg").is_file()


def test_tidy_the_root(engine: Engine) -> None:
    with pytest.raises(ActionNotAllowedError) as exc:
        engine.action_tidy("")
    assert exc.value.kind == "root"


@pytest.mark.internal
def test_publish_folder_typed_in_lower_case_is_guarded(
    roots: Roots, engine: Engine
) -> None:
    (roots.darkroom / BATCH / PUBLISH_FOLDER).mkdir(parents=True)
    with pytest.raises(ActionNotAllowedError) as exc:
        engine.action_tidy(f"{BATCH}/publish")
    assert exc.value.kind == "publish"


# ---------------------------------------------------------------------------
# Creating a missing node
# ---------------------------------------------------------------------------


def test_new_batch_for_a_new_device(roots: Roots, engine: Engine) -> None:
    plan = _plan(engine.action_new_batch("Drone", date="2027-01"))
    drone = roots.darkroom / "Drone"
    assert plan.steps == (
        MakeDir(drone),
        MakeDir(drone / "2027"),
        MakeDir(drone / "2027/2027-01"),
        MakeDir(drone / "2027/2027-01" / PUBLISH_FOLDER),
    )
    assert not drone.exists()


@pytest.mark.internal
def test_only_new_batch_creates_its_folder(engine: Engine) -> None:
    with pytest.raises(NodeNotFoundError):
        engine.action_open("Drone")


# ---------------------------------------------------------------------------
# External app commands come from configuration
# ---------------------------------------------------------------------------


def test_cull_without_a_command(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    out = engine.action_cull(BATCH).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert "cull_command" in out.message


def test_edit_runs_the_configured_command(roots: Roots, make_engine) -> None:
    folder = _batch(roots)
    engine = make_engine(roots, edit_command='editor --open "{folder}"')
    plan = _plan(engine.action_edit(BATCH))
    assert plan.steps == (Launch(("editor", "--open", str(folder.resolve()))),)


# ---------------------------------------------------------------------------
# Preparing yields a plan or an outcome; plans say whether they change files
# ---------------------------------------------------------------------------


def test_rename_plan(roots: Roots, engine: Engine) -> None:
    old = _batch(roots)
    plan = _plan(engine.action_rename(BATCH, date="2026-10-05"))
    assert plan.steps == (Rename(old, old.with_name("2026-10-05 Walk")),)


def test_nothing_to_tidy(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    out = engine.action_tidy(BATCH).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "noop"


def test_launching_an_app(roots: Roots, make_engine: MakeEngine) -> None:
    _batch(roots)
    engine = make_engine(roots, edit_command="editor {folder}")
    assert not _plan(engine.action_edit(BATCH)).changes_files


def test_archive_changes_files(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    assert _plan(engine.action_archive(BATCH)).changes_files


# ---------------------------------------------------------------------------
# Plans carry a fingerprint
# ---------------------------------------------------------------------------


def test_same_request_twice(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg", "b.jpg")
    first = _plan(engine.action_archive(BATCH)).fingerprint
    second = _plan(engine.action_archive(BATCH)).fingerprint
    assert first == second


def test_same_request_in_another_engine(roots: Roots, make_engine) -> None:
    _batch(roots, "a.jpg")
    first = _plan(make_engine(roots).action_archive(BATCH)).fingerprint
    second = _plan(make_engine(roots).action_archive(BATCH)).fingerprint
    assert first == second


def test_file_added_in_between(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    first = _plan(engine.action_archive(BATCH)).fingerprint
    (batch / "b.jpg").write_bytes(b"")
    assert _plan(engine.action_archive(BATCH)).fingerprint != first


# ---------------------------------------------------------------------------
# Applying an action; confirming a plan
# ---------------------------------------------------------------------------


def test_apply_at_once(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    result = engine.action_apply(engine.action_tidy(BATCH))
    assert result.outcome == "ok"
    assert (batch / "PHOTOS/a.jpg").is_file()
    assert result.fingerprint is not None


def test_plan_changed_since_the_preview(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    shown = _plan(engine.action_archive(BATCH)).fingerprint
    (batch / "b.jpg").write_bytes(b"")

    result = engine.action_apply(engine.action_archive(BATCH), confirm=shown)

    assert result.outcome == "refused"
    assert shown in result.message
    assert result.fingerprint is not None
    assert result.fingerprint != shown
    assert result.fingerprint in result.message
    assert (batch / "a.jpg").is_file()
    assert not any(roots.archive.rglob("*.jpg"))


def test_plan_unchanged(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    shown = _plan(engine.action_archive(BATCH)).fingerprint
    result = engine.action_apply(engine.action_archive(BATCH), confirm=shown)
    assert result.outcome == "ok"
    assert (roots.archive / "2026/2026-10 Walk/Camera/a.jpg").is_file()


def test_apply_returns_a_prepare_outcome(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    result = engine.action_apply(engine.action_tidy(BATCH))
    assert result.outcome == "noop"
    assert result.fingerprint is None


@pytest.mark.internal
def test_apply_on_a_busy_engine(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots, "a.jpg")
    action = engine.action_tidy(BATCH)
    started = threading.Event()
    release = threading.Event()
    real_prepare = TidyAction._prepare

    def slow_prepare(self):
        started.set()
        release.wait(5)
        return real_prepare(self)

    monkeypatch.setattr(TidyAction, "_prepare", slow_prepare)
    worker = threading.Thread(target=engine.action_apply, args=(action,))
    worker.start()
    try:
        assert started.wait(5)
        with pytest.raises(EngineBusyError) as exc:
            engine.action_apply(engine.action_tidy(BATCH))
        assert exc.value.job.name == "tidy"
    finally:
        release.set()
        worker.join(5)
    assert (roots.darkroom / BATCH / "PHOTOS/a.jpg").is_file()


# ---------------------------------------------------------------------------
# Outcome kinds
# ---------------------------------------------------------------------------


def test_conflict_at_prepare(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    taken = roots.archive / "2026/2026-10 Walk/Camera/a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    out = engine.action_archive(BATCH).prepare()
    assert isinstance(out, ActionPlan)
    assert [c.move.source.name for c in out.conflicts] == ["a.jpg"]
    assert out.steps == ()


def test_unexpected_error(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots, "a.jpg")

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(actions_module, "move_files", boom)
    result = engine.action_apply(engine.action_archive(BATCH))
    assert result.outcome == "failed"
    assert result.details is not None
    assert "disk on fire" in result.details


# ---------------------------------------------------------------------------
# Results name the node after the action
# ---------------------------------------------------------------------------


def test_results_name_the_renamed_node(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    result = engine.action_apply(engine.action_rename(BATCH, date="2026-10-05"))
    assert result.outcome == "ok"
    assert result.node_id == "Camera/2026/2026-10-05 Walk"


def test_archive_empties_the_batch(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    result = engine.action_apply(engine.action_archive(BATCH))
    assert result.outcome == "ok"
    assert result.node_id is None


@pytest.mark.internal
def test_new_batch_names_the_new_batch(engine: Engine) -> None:
    result = engine.action_apply(engine.action_new_batch("camera", date="2026-10"))
    assert result.node_id == "camera/2026/2026-10"
