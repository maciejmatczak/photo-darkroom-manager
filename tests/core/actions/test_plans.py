"""Tests for action requests, plans, fingerprints and results."""

from dataclasses import replace
from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionRequest,
    ActionResult,
    ArchiveAction,
    Conflict,
    ExecutionResult,
    JobAction,
    Launch,
    MakeDir,
    Move,
    NewBatchAction,
    OpenFolder,
    OpenFolderAction,
    PolicyNotSupportedError,
    PublishAction,
    Rename,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.core.jobs import Job, JobCancelled
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


def test_preview_lists_steps_and_conflicts() -> None:
    moves = [Move(Path(f"/s/{i:03}.jpg"), Path(f"/t/{i:03}.jpg")) for i in range(40)]
    conflicts = tuple(
        Conflict(Move(Path(f"/s/z{i:02}.jpg"), Path(f"/t/z{i:02}.jpg")), "exists")
        for i in range(37)
    )
    plan = ActionPlan(
        REQUEST,
        "Publish 77 files",
        tuple(moves),
        bases=(Path("/s"),),
        conflicts=conflicts,
        conflict_label="replace",
    )
    text = plan.preview_text()
    assert text.startswith("Publish 77 files")
    assert "Steps: 40 move" in text
    assert f"move 000.jpg → {Path('/t/000.jpg')}" in text
    assert "… and 5 more" in text
    assert "Conflicts (replace): 37" in text
    assert "replace z00.jpg" in text
    assert "… and 2 more" in text
    assert "039.jpg" not in text
    assert "z36.jpg" not in text


def test_fingerprint_covers_conflicts() -> None:
    move = Move(Path("/d/a.jpg"), Path("/d/PHOTOS/a.jpg"))
    base = _plan(move)
    with_conflict = ActionPlan(
        REQUEST,
        "summary",
        (move,),
        conflicts=(Conflict(Move(Path("/d/b.jpg"), Path("/x/b.jpg")), "exists"),),
    )
    other_reason = replace(
        with_conflict,
        conflicts=(Conflict(Move(Path("/d/b.jpg"), Path("/x/b.jpg")), "same_target"),),
    )
    assert (
        len({base.fingerprint, with_conflict.fingerprint, other_reason.fingerprint})
        == 3
    )


def test_policies_per_action() -> None:
    assert ArchiveAction.policies == ("refuse", "skip")
    assert TidyAction.policies == ("refuse", "skip")
    assert PublishAction.policies == ("refuse", "skip", "replace")


def test_heavy_actions_are_job_actions_and_exclusive() -> None:
    for heavy in (TidyAction, ArchiveAction, PublishAction):
        assert issubclass(heavy, JobAction)
        assert heavy.exclusive
    for alone in (RenameAction, NewBatchAction):
        assert not issubclass(alone, JobAction)
        assert alone.exclusive
    assert not OpenFolderAction.exclusive


def test_unsupported_policy_is_a_typed_error(tmp_path: Path) -> None:
    action = TidyAction(tmp_path, request=ActionRequest.of(A.TIDY, "x"))
    with pytest.raises(PolicyNotSupportedError) as err:
        action.check_policy("replace")
    assert err.value.supported == ("refuse", "skip")
    assert "refuse, skip" in str(err.value)
    assert action.check_policy("skip") == "skip"


def test_stop_between_steps_reports_done_and_left(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"{i}.jpg").write_bytes(b"")
    action = TidyAction(tmp_path)
    plan = action.prepare()
    assert isinstance(plan, ActionPlan)
    reported: list[tuple[int, int | None, str | None]] = []

    class CancelAfterTwo(Job):
        def progress(
            self, done: int, total: int | None = None, current: str | None = None
        ) -> None:
            super().progress(done, total, current)
            reported.append((done, total, current))
            if done >= 2:
                self.cancel()

    log_path = tmp_path / "logs" / "tidy.log"
    log_path.parent.mkdir()
    job = CancelAfterTwo("tidy", log_path=log_path)
    with pytest.raises(JobCancelled) as stopped:
        action.execute(plan, job=job)
    job.close()

    result = stopped.value.result
    assert isinstance(result, ExecutionResult)
    assert result.outcome == "cancelled"
    assert len(result.done) == 2
    assert sorted(p.name for p in result.left) == ["2.jpg", "3.jpg", "4.jpg"]
    assert reported[0] == (0, 5, None)
    assert reported[1][:2] == (1, 5)
    assert "cancelled" in result.message
    assert log_path.read_text(encoding="utf-8").count("event='step_done'") == 2


def test_conflicts_left_undone_reach_the_job_log(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"loose")
    (tmp_path / "PHOTOS").mkdir()
    (tmp_path / "PHOTOS" / "a.jpg").write_bytes(b"other")
    action = TidyAction(tmp_path)
    plan = action.prepare()
    assert isinstance(plan, ActionPlan)
    log_path = tmp_path / "logs" / "tidy.log"
    log_path.parent.mkdir()
    job = Job("tidy", log_path=log_path)

    action.execute(plan, policy="skip", job=job)
    job.close()

    (line,) = log_path.read_text(encoding="utf-8").splitlines()
    assert "event='step_skipped'" in line
    assert "a.jpg" in line
    assert "reason='conflict (exists)'" in line


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
    result = action.execute(foreign, job=Job("tidy"))
    assert result.outcome == "refused"
    assert (tmp_path / "a.jpg").exists()


def test_execute_lets_errors_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.jpg").write_bytes(b"")
    action = TidyAction(tmp_path)
    plan = action.prepare()
    assert isinstance(plan, ActionPlan)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(TidyAction, "_run", boom)
    with pytest.raises(RuntimeError, match="boom"):
        action.execute(plan, job=Job("tidy"))
