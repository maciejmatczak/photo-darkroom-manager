"""Contract: engine/actions and engine/planned-actions, through the engine."""

from pathlib import Path

import pytest
from conftest import MakeEngine, Roots, run_planned

from photo_darkroom_manager.core.actions import _moves as moves_module
from photo_darkroom_manager.core.actions import apps as apps_module
from photo_darkroom_manager.core.engine import (
    ActionNotAllowedError,
    ActionRefusedError,
    Engine,
    NodeNotFoundError,
)
from photo_darkroom_manager.core.library import PUBLISH_FOLDER, NodeAction

BATCH = "Camera/2026/2026-10 Walk"
ARCHIVED = Path("2026/2026-10 Walk/Camera")


def _batch(roots: Roots, *files: str) -> Path:
    path = roots.darkroom / BATCH
    path.mkdir(parents=True)
    for name in files:
        (path / name).write_bytes(name.encode())
    return path


# ---------------------------------------------------------------------------
# Actions address a node by id
# ---------------------------------------------------------------------------


def test_archive_without_a_scan(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    plan = engine.action_prepare_archive(BATCH)
    assert plan.source == batch
    assert not engine.library_scanned


def test_id_outside_the_library_layout(roots: Roots, engine: Engine) -> None:
    (roots.darkroom / "Camera/notes").mkdir(parents=True)
    with pytest.raises(NodeNotFoundError) as exc:
        engine.action_prepare_tidy("Camera/notes")
    assert exc.value.node_id == "Camera/notes"


def test_folder_gone(engine: Engine) -> None:
    with pytest.raises(NodeNotFoundError) as exc:
        engine.action_prepare_archive(BATCH)
    assert exc.value.node_id == BATCH


@pytest.mark.internal
@pytest.mark.parametrize("node_id", ["..", "Camera/../x", "/Camera", "C:/x"])
def test_malformed_ids_are_not_found(engine: Engine, node_id: str) -> None:
    with pytest.raises(NodeNotFoundError):
        engine.action_open(node_id)


def test_ids_follow_on_disk_names(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    assert engine.action_prepare_tidy(BATCH.lower()).folder == batch


# ---------------------------------------------------------------------------
# Actions are guarded by node kind
# ---------------------------------------------------------------------------


def test_archive_a_year(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    with pytest.raises(ActionNotAllowedError) as exc:
        engine.action_prepare_archive("Camera/2026")
    assert (exc.value.node_id, exc.value.action, exc.value.kind) == (
        "Camera/2026",
        NodeAction.ARCHIVE,
        "year",
    )
    assert (roots.darkroom / BATCH / "a.jpg").is_file()


def test_tidy_the_root(engine: Engine) -> None:
    with pytest.raises(ActionNotAllowedError) as exc:
        engine.action_prepare_tidy("")
    assert exc.value.kind == "root"


@pytest.mark.internal
def test_publish_folder_typed_in_lower_case_is_guarded(
    roots: Roots, engine: Engine
) -> None:
    (roots.darkroom / BATCH / PUBLISH_FOLDER).mkdir(parents=True)
    with pytest.raises(ActionNotAllowedError) as exc:
        engine.action_prepare_tidy(f"{BATCH}/publish")
    assert exc.value.kind == "publish"


# ---------------------------------------------------------------------------
# Creating a missing node
# ---------------------------------------------------------------------------


def test_new_batch_for_a_new_device(roots: Roots, engine: Engine) -> None:
    plan = engine.action_prepare_new_batch("Drone", date="2027-01")
    drone = roots.darkroom / "Drone"
    assert plan.folders_to_create == (
        drone,
        drone / "2027",
        drone / "2027/2027-01",
        drone / "2027/2027-01" / PUBLISH_FOLDER,
    )
    assert not drone.exists()


@pytest.mark.internal
def test_only_new_batch_creates_its_folder(engine: Engine) -> None:
    with pytest.raises(NodeNotFoundError):
        engine.action_open("Drone")


# ---------------------------------------------------------------------------
# Direct actions; external app commands come from configuration
# ---------------------------------------------------------------------------


def test_open_returns_its_result_and_starts_no_job(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = _batch(roots)
    opened: list[Path] = []
    monkeypatch.setattr(apps_module, "_open_in_file_manager", opened.append)
    result = engine.action_open(BATCH)
    assert result.outcome == "ok"
    assert result.folder == batch
    assert opened == [batch]
    assert engine.job is None


def test_cull_without_a_command(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    with pytest.raises(ActionRefusedError, match="cull_command"):
        engine.action_cull(BATCH)


def test_edit_runs_the_configured_command(
    roots: Roots, make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = _batch(roots)
    started: list[tuple[str, ...]] = []

    class _Running:
        def wait(self, timeout: float) -> int:
            raise apps_module.subprocess.TimeoutExpired("editor", timeout)

    def fake_popen(argv: tuple[str, ...], **_kw: object) -> _Running:
        started.append(argv)
        return _Running()

    monkeypatch.setattr(apps_module.subprocess, "Popen", fake_popen)
    engine = make_engine(roots, edit_command='editor --open "{folder}"')
    result = engine.action_edit(BATCH)
    assert result.outcome == "ok"
    assert started == [("editor", "--open", str(folder.resolve()))]
    assert engine.job is None


# ---------------------------------------------------------------------------
# Preparing yields a plan or a refusal
# ---------------------------------------------------------------------------


def test_rename_plan(roots: Roots, engine: Engine) -> None:
    old = _batch(roots)
    plan = engine.action_prepare_rename(BATCH, date="2026-10-05")
    assert plan.new_folder == old.with_name("2026-10-05 Walk")


def test_nothing_to_tidy(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    assert engine.action_prepare_tidy(BATCH).nothing_to_do


def test_a_taken_name_is_refused(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    (roots.darkroom / "Camera/2026/2026-10 Hike").mkdir()
    with pytest.raises(ActionRefusedError, match="2026-10 Hike"):
        engine.action_prepare_rename(BATCH, title="Hike")


# ---------------------------------------------------------------------------
# Plans carry a fingerprint
# ---------------------------------------------------------------------------


def test_same_preparation_twice(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg", "b.jpg")
    first = engine.action_prepare_archive(BATCH).fingerprint
    assert engine.action_prepare_archive(BATCH).fingerprint == first


def test_same_preparation_in_another_engine(roots: Roots, make_engine) -> None:
    _batch(roots, "a.jpg")
    first = make_engine(roots).action_prepare_archive(BATCH).fingerprint
    assert make_engine(roots).action_prepare_archive(BATCH).fingerprint == first


def test_file_added_in_between(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    first = engine.action_prepare_archive(BATCH).fingerprint
    (batch / "b.jpg").write_bytes(b"")
    assert engine.action_prepare_archive(BATCH).fingerprint != first


# ---------------------------------------------------------------------------
# Executing a plan; answers are checked before running
# ---------------------------------------------------------------------------


def test_an_unchanged_plan_runs_as_a_job(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    done = run_planned(engine, "tidy", BATCH)
    assert done.result.outcome == "ok"
    assert (batch / "PHOTOS/a.jpg").is_file()
    assert engine.job is not None and engine.job.name == "tidy"


def test_plan_changed_since_the_preview(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    shown = engine.action_prepare_archive(BATCH)
    (batch / "b.jpg").write_bytes(b"")
    current = engine.action_prepare_archive(BATCH).fingerprint

    with pytest.raises(ActionRefusedError) as refused:
        engine.action_archive(shown)

    assert shown.fingerprint in refused.value.message
    assert current in refused.value.message
    assert engine.job is None
    assert (batch / "a.jpg").is_file()
    assert not any(roots.archive.rglob("*.jpg"))


def test_a_republish_without_a_choice_is_refused(roots: Roots, engine: Engine) -> None:
    publish_folder = _batch(roots) / PUBLISH_FOLDER
    publish_folder.mkdir()
    (publish_folder / "a.jpg").write_bytes(b"new")
    taken = roots.showroom / ARCHIVED / "a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    plan = engine.action_prepare_publish(BATCH)
    with pytest.raises(ActionRefusedError, match="existing"):
        engine.action_publish(plan)
    assert engine.job is None
    assert taken.read_bytes() == b"old"


def test_an_answer_the_question_does_not_offer_is_refused(
    roots: Roots, engine: Engine
) -> None:
    _batch(roots, "a.jpg")
    taken = roots.archive / ARCHIVED / "a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    plan = engine.action_prepare_archive(BATCH)
    with pytest.raises(ActionRefusedError, match="replace"):
        engine.action_archive(plan, {"existing": "replace"})
    assert taken.read_bytes() == b"old"


def test_a_conflict_listed_at_prepare(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    taken = roots.archive / ARCHIVED / "a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    plan = engine.action_prepare_archive(BATCH)
    assert [c.source.name for c in plan.conflicts] == ["a.jpg"]
    assert plan.moves == ()


def test_unexpected_error(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots, "a.jpg")

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(moves_module, "move_files", boom)
    with pytest.raises(RuntimeError, match="disk on fire"):
        run_planned(engine, "archive", BATCH)
    job = engine.job
    assert job is not None and job.state == "failed"
    assert job.error == "RuntimeError: disk on fire"


# ---------------------------------------------------------------------------
# Results name the node after the action
# ---------------------------------------------------------------------------


def test_results_name_the_renamed_node(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    done = run_planned(engine, "rename", BATCH, date="2026-10-05")
    assert done.result.outcome == "ok"
    assert done.node_id == "Camera/2026/2026-10-05 Walk"


def test_archive_empties_the_batch(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    done = run_planned(engine, "archive", BATCH)
    assert done.result.outcome == "ok"
    assert done.node_id is None


def test_the_action_result_is_untouched(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    done = run_planned(engine, "tidy", BATCH)
    assert done.result.folder == roots.darkroom / BATCH
    assert not hasattr(done.result, "node_id")


@pytest.mark.internal
def test_new_batch_names_the_new_batch(engine: Engine) -> None:
    done = run_planned(engine, "new_batch", "camera", date="2026-10")
    assert done.node_id == "camera/2026/2026-10"
