"""Tests for action requests, plans, fingerprints and results."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionRequest,
    ActionResult,
    ExecutionResult,
    Launch,
    MakeDir,
    Move,
    OpenFolder,
    Rename,
    TidyAction,
)
from photo_darkroom_manager.core.library import NodeAction

pytestmark = pytest.mark.internal

A = NodeAction
REQUEST = ActionRequest.of(A.RENAME, "Camera/2026/2026-10 Walk", title="Hike")


def _plan(*steps, request: ActionRequest = REQUEST) -> ActionPlan:
    return ActionPlan(request, "summary", tuple(steps))


def test_request_params_are_sorted() -> None:
    a = ActionRequest.of(A.RENAME, "x", title="t", date="2026-10")
    b = ActionRequest.of(A.RENAME, "x", date="2026-10", title="t")
    assert a == b
    assert a.params == (("date", "2026-10"), ("title", "t"))


def test_fingerprint_is_stable_for_equal_plans() -> None:
    steps = (Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg")),)
    first = _plan(*steps)
    second = ActionPlan(REQUEST, "other summary", steps, notes=("ignored",))
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 12
    assert int(first.fingerprint, 16) >= 0


@pytest.mark.parametrize(
    "other",
    [
        _plan(Move(Path("/d/b.jpg"), Path("/d/PHOTOS/b.jpg"))),
        _plan(Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg"), overwrite=True)),
        _plan(
            Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg")),
            Move(Path("/d/c.jpg"), Path("/d/PHOTOS/c.jpg")),
        ),
        _plan(Move(Path("/other-root/a.jpg"), Path("/other-root/PHOTOS/a.jpg"))),
        _plan(
            Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg")),
            request=ActionRequest.of(A.RENAME, "Camera/2026/2026-10 Walk", title="X"),
        ),
        _plan(
            Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg")),
            request=ActionRequest.of(A.TIDY, "Camera/2026/2026-10 Walk", title="Hike"),
        ),
        _plan(
            Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg")),
            request=ActionRequest.of(A.RENAME, "Camera/2026/2026-11", title="Hike"),
        ),
    ],
)
def test_fingerprint_changes_with_any_step_param_or_root(other: ActionPlan) -> None:
    base = _plan(Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg")))
    assert other.fingerprint != base.fingerprint


@pytest.mark.parametrize(
    ("step", "changes"),
    [
        (Move(Path("/a"), Path("/b")), True),
        (MakeDir(Path("/a")), True),
        (Rename(Path("/a"), Path("/b")), True),
        (OpenFolder(Path("/a")), False),
        (Launch(("edit", "/a")), False),
    ],
)
def test_changes_files_by_step_kind(step, changes: bool) -> None:
    assert _plan(step).changes_files is changes


def test_preview_lists_steps_and_every_overwrite() -> None:
    moves = [Move(Path(f"/s/{i:03}.jpg"), Path(f"/t/{i:03}.jpg")) for i in range(40)]
    moves.append(Move(Path("/s/zz.jpg"), Path("/t/zz.jpg"), overwrite=True))
    plan = ActionPlan(REQUEST, "Publish 41 files", tuple(moves), bases=(Path("/s"),))
    text = plan.preview_text()
    assert text.startswith("Publish 41 files")
    assert "Steps: 40 move, 1 overwrite" in text
    assert f"move 000.jpg → {Path('/t/000.jpg')}" in text
    assert "… and 6 more" in text
    assert "overwrite zz.jpg" in text
    assert "039.jpg" not in text


def test_success_follows_the_outcome() -> None:
    assert ActionResult("ok", "").success
    assert ActionResult("noop", "").success
    assert not ActionResult("refused", "").success
    assert not ExecutionResult("failed", "").success


def test_execute_refuses_a_plan_for_another_request(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"")
    action = TidyAction(tmp_path, request=ActionRequest.of(A.TIDY, "x"))
    plan = action.prepare()
    assert isinstance(plan, ActionPlan)
    foreign = ActionPlan(ActionRequest.of(A.TIDY, "y"), plan.summary, plan.steps)
    result = action.execute(foreign)
    assert result.outcome == "refused"
    assert (tmp_path / "a.jpg").exists()


def test_execute_wraps_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.jpg").write_bytes(b"")
    action = TidyAction(tmp_path)
    plan = action.prepare()
    assert isinstance(plan, ActionPlan)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(TidyAction, "_execute", boom)
    result = action.execute(plan)
    assert result.outcome == "failed"
    assert result.details is not None
    assert "RuntimeError" in result.details
    assert result.fingerprint == plan.fingerprint
