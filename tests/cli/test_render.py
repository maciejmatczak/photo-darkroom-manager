"""Tests for the CLI's renderers of typed action plans and results."""

import json
from pathlib import Path

import pytest

from photo_darkroom_manager.cli import _render
from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    apps,
    archive,
    new_batch,
    publish,
    rename,
    tidy,
)
from photo_darkroom_manager.core.actions._moves import (
    CONFLICT_EXISTS,
    FileMove,
    MoveReport,
)

SRC = Path("/dark/Camera/2026/2026-10 Walk")
DST = Path("/archive/2026/2026-10 Walk/Camera")


def _all_subclasses(cls: type) -> set[type]:
    found = set()
    for sub in cls.__subclasses__():
        found |= {sub, *_all_subclasses(sub)}
    return found


def _typed(cls: type) -> set[type]:
    """Subclasses defined by the action modules, not by tests."""
    return {
        c
        for c in _all_subclasses(cls)
        if c.__module__.startswith("photo_darkroom_manager.core.actions")
    }


def test_every_plan_type_has_a_text_and_a_json_renderer() -> None:
    plan_types = _typed(ActionPlan)
    assert plan_types == set(_render._PLAN_TEXT) == set(_render._PLAN_DATA)


def test_every_result_type_has_a_text_and_a_json_renderer() -> None:
    result_types = _typed(ActionResult)
    assert result_types == set(_render._RESULT_TEXT) == set(_render._RESULT_DATA)


def _archive_plan(conflicts: int = 0) -> archive.ArchivePlan:
    moves = tuple(FileMove(SRC / f"{i}.jpg", DST / f"{i}.jpg") for i in range(2))
    taken = tuple(
        FileMove(SRC / f"x{i}.jpg", DST / f"x{i}.jpg", CONFLICT_EXISTS)
        for i in range(conflicts)
    )
    questions = (
        {archive.EXISTING_QUESTION: archive.Question("1 file there", ("skip",))}
        if conflicts
        else {}
    )
    return archive.ArchivePlan(
        SRC, DST, Path("/dark"), Path("/archive"), moves, taken, questions=questions
    )


def test_an_archive_plan_in_text() -> None:
    text = _render.action_plan_text(_archive_plan(1), "darkroom archive x --confirm f")
    assert "Archive 2 files, 1 already in the archive" in text
    assert "move 0.jpg → 0.jpg" in text
    assert "Already in the archive: 1" in text
    assert "existing: 1 file there (skip)" in text
    assert f"plan {_archive_plan(1).fingerprint}" in text
    assert "run it: darkroom archive x --confirm f" in text


def test_an_archive_plan_in_json() -> None:
    plan = _archive_plan(1)
    data = json.loads(
        json.dumps(_render.action_plan_data("archive", "C/2026/W", plan, ["darkroom"]))
    )
    assert data["kind"] == "plan"
    assert data["action"] == "archive"
    assert data["node_id"] == "C/2026/W"
    assert data["source"] == SRC.as_posix()
    assert len(data["moves"]) == 2
    assert data["conflicts"][0]["reason"] == CONFLICT_EXISTS
    assert data["questions"]["existing"]["choices"] == ["skip"]
    assert data["fingerprint"] == plan.fingerprint
    assert data["nothing_to_do"] is False


def test_nothing_to_do_prints_no_run_command() -> None:
    plan = tidy.TidyPlan(SRC, ())
    text = _render.action_plan_text(plan, None)
    assert text.startswith("Nothing to tidy")
    assert "run it" not in text


@pytest.mark.parametrize(
    ("plan", "first_line"),
    [
        (
            tidy.TidyPlan(SRC, (FileMove(SRC / "a.jpg", SRC / "PHOTOS/a.jpg"),)),
            "Tidy 1",
        ),
        (
            publish.PublishPlan(
                SRC, SRC / "PUBLISH", DST, Path("/dark"), Path("/show"), ()
            ),
            "Nothing to publish",
        ),
        (
            rename.RenamePlan(
                SRC, Path("/dark"), None, "Hike", False, SRC.with_name("2026-10 Hike")
            ),
            "Rename 2026-10 Walk to 2026-10 Hike",
        ),
        (
            new_batch.NewBatchPlan(
                Path("/dark"),
                "Drone",
                "2027-01",
                None,
                Path("/dark/Drone/2027/2027-01"),
                (Path("/dark/Drone"),),
            ),
            "Create batch Drone/2027/2027-01",
        ),
    ],
)
def test_each_plan_speaks_its_own_terms(plan: ActionPlan, first_line: str) -> None:
    assert _render.action_plan_text(plan, None).startswith(first_line)
    json.dumps(_render.action_plan_data("x", "", plan, None))


def test_an_archive_result_in_text_and_json() -> None:
    report = MoveReport(
        moved=(FileMove(SRC / "a.jpg", DST / "a.jpg"),),
        skipped=(FileMove(SRC / "b.jpg", DST / "b.jpg", CONFLICT_EXISTS),),
    )
    result = archive.ArchiveResult(
        outcome="ok",
        message="Archived 1 of 2 file(s); 1 skipped as conflicts",
        source=SRC,
        moves=report,
        remaining=(SRC / "b.jpg",),
    )
    text = _render.action_result_text(result, "Camera/2026/2026-10 Walk")
    assert text.startswith("ok: Archived 1 of 2 file(s)")
    assert "skipped: 1 conflict(s)" in text
    assert "remaining: 1 file(s)" in text
    assert "node: Camera/2026/2026-10 Walk" in text
    data = json.loads(
        json.dumps(_render.action_result_data("archive", result, None, "Camera/2026"))
    )
    assert data["outcome"] == "ok"
    assert len(data["moves"]["skipped"]) == 1
    assert data["library_refreshed"] == "Camera/2026"


def test_a_direct_result_in_text() -> None:
    result = apps.ExternalAppResult(
        outcome="failed",
        message="Command exited with code 7",
        folder=SRC,
        command=("editor", "x"),
        exit_code=7,
    )
    text = _render.action_result_text(result)
    assert text.startswith("failed: Command exited with code 7")
    assert "command: editor x" in text
