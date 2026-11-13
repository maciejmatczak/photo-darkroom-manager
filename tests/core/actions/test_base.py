"""Tests for the shared foundation: plans, fingerprints, answers, refusals."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionRefusedError,
    Question,
    check_answers,
    fingerprint,
    require_unchanged_plan,
)

SKIP_OR_REPLACE = Question("2 files already there", ("replace", "skip"))


@dataclass(frozen=True)
class _CopyPlan(ActionPlan):
    folder: Path
    files: tuple[str, ...]

    @property
    def nothing_to_do(self) -> bool:
        return not self.files


def test_equal_parts_give_equal_fingerprints() -> None:
    parts = (Path("a/b"), {"x": 1}, ("c", "d"))
    assert fingerprint(*parts) == fingerprint(*parts)
    assert len(fingerprint(*parts)) == 12


def test_any_changed_part_gives_another_fingerprint() -> None:
    base = fingerprint(Path("a"), ("c",), SKIP_OR_REPLACE)
    assert fingerprint(Path("b"), ("c",), SKIP_OR_REPLACE) != base
    assert fingerprint(Path("a"), ("c", "d"), SKIP_OR_REPLACE) != base
    assert fingerprint(Path("a"), ("c",), Question("x", ("skip",))) != base


def test_a_plan_fingerprints_its_fields_and_questions() -> None:
    plan = _CopyPlan(Path("f"), ("a.jpg",))
    assert plan.fingerprint == _CopyPlan(Path("f"), ("a.jpg",)).fingerprint
    assert plan.fingerprint != _CopyPlan(Path("f"), ("a.jpg", "b.jpg")).fingerprint
    asked = _CopyPlan(Path("f"), ("a.jpg",), questions={"existing": SKIP_OR_REPLACE})
    assert asked.fingerprint != plan.fingerprint


def test_nothing_to_do_is_still_a_plan() -> None:
    assert _CopyPlan(Path("f"), ()).nothing_to_do
    assert not _CopyPlan(Path("f"), ("a.jpg",)).nothing_to_do


def test_an_unchanged_plan_passes() -> None:
    plan = _CopyPlan(Path("f"), ("a.jpg",))
    require_unchanged_plan(plan, _CopyPlan(Path("f"), ("a.jpg",)))


def test_a_changed_plan_is_refused_naming_both_fingerprints() -> None:
    plan = _CopyPlan(Path("f"), ("a.jpg",))
    fresh_plan = _CopyPlan(Path("f"), ("a.jpg", "late.jpg"))
    with pytest.raises(ActionRefusedError) as refused:
        require_unchanged_plan(plan, fresh_plan)
    assert plan.fingerprint in refused.value.message
    assert fresh_plan.fingerprint in refused.value.message


def test_an_answer_is_one_of_the_choices() -> None:
    questions = {"existing": SKIP_OR_REPLACE}
    assert check_answers(questions, {"existing": "replace"}) == {"existing": "replace"}


def test_an_unanswered_question_takes_its_default() -> None:
    questions = {"existing": Question("x", ("skip",), default="skip")}
    assert check_answers(questions, {}) == {"existing": "skip"}


def test_no_answer_without_a_default_is_refused() -> None:
    with pytest.raises(ActionRefusedError, match="existing"):
        check_answers({"existing": SKIP_OR_REPLACE}, {})


def test_a_choice_not_offered_is_refused() -> None:
    with pytest.raises(ActionRefusedError, match="existing"):
        check_answers({"existing": SKIP_OR_REPLACE}, {"existing": "merge"})


def test_an_unknown_question_is_refused() -> None:
    with pytest.raises(ActionRefusedError, match="colour"):
        check_answers({}, {"colour": "red"})


def test_no_questions_need_no_answers() -> None:
    assert check_answers({}, {}) == {}
