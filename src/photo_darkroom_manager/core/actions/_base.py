"""The shared foundation every action may build on.

Every action has a result; some have a plan; some run as a job. This module
gives the types and helpers for that, and no common interface to execute an
action: each action has its own functions and the engine its own calls.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Outcome = Literal["ok", "failed", "cancelled"]
"""How an attempted action ended; a refusal raises instead."""

Answers = Mapping[str, str]
"""Posted form data: question name to the chosen answer."""

_FINGERPRINT_LENGTH = 12


@dataclass(frozen=True, kw_only=True)
class ActionResult:
    """What an action that was attempted did; each action has its own subclass.

    Args:
        outcome: ``ok`` when it did what was asked, ``failed`` when something
            went wrong while running, ``cancelled`` when a client stopped it.
        message: One line saying what happened.
    """

    outcome: Outcome
    message: str


@dataclass(frozen=True)
class Question:
    """One form field with choices, asked before a planned action runs.

    Args:
        text: What the user decides, e.g. ``3 files already in the showroom``.
        choices: The answers the action accepts, e.g. ``("replace", "skip")``.
        default: The answer when none is given; ``None``: the user must answer.
    """

    text: str
    choices: tuple[str, ...]
    default: str | None = None


@dataclass(frozen=True, kw_only=True)
class ActionPlan(ABC):
    """What a planned action will do, in its own terms; plain data.

    Each planned action has its own subclass whose fields describe the work
    and carry the inputs to prepare it again. Every field, the questions
    included, goes into the fingerprint, so any change in what the action
    would do or ask gives a different one.

    Args:
        questions: What the user must decide before it runs, by name.
    """

    questions: Mapping[str, Question] = dataclasses.field(default_factory=dict)

    @property
    @abstractmethod
    def nothing_to_do(self) -> bool:
        """True when running the plan would change nothing."""

    @property
    def fingerprint(self) -> str:
        """Short digest of every field; same fingerprint, same plan."""
        return fingerprint(type(self).__name__, self)


class ActionRefusedError(Exception):
    """An action cannot plan or run as asked; nothing was changed.

    Args:
        message: One line saying why.
        details: More lines, e.g. the files in the way; ``None`` if none.
    """

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def _plain(value: object) -> object:
    """*value* as JSON data: paths as POSIX text, dataclasses as dicts."""
    if isinstance(value, Path):
        return value.as_posix()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, set | frozenset):
        return sorted((_plain(v) for v in value), key=json.dumps)
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def fingerprint(*parts: object) -> str:
    """Short digest of *parts*; equal parts give equal fingerprints in any process.

    Args:
        parts: Values to hash: paths, dataclasses, mappings, sequences or
            plain values.
    """
    text = json.dumps(_plain(parts), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]


def require_unchanged_plan(plan: ActionPlan, fresh_plan: ActionPlan) -> None:
    """Refuse a plan handed back that differs from the one prepared now.

    Args:
        plan: The plan the client was shown and handed back.
        fresh_plan: The same action prepared again just now.

    Raises:
        ActionRefusedError: The fingerprints differ; the message names both.
    """
    if plan.fingerprint != fresh_plan.fingerprint:
        raise ActionRefusedError(
            f"plan changed since {plan.fingerprint} "
            f"(now {fresh_plan.fingerprint}); prepare again"
        )


def check_answers(questions: Mapping[str, Question], answers: Answers) -> Answers:
    """Apply the form rules to *answers*; return them with defaults filled in.

    An answer must name one of *questions* and be one of its choices; a
    question left unanswered takes its default.

    Args:
        questions: The plan's questions, by name.
        answers: What the client posted, by question name.

    Raises:
        ActionRefusedError: An unknown question, a choice the question does
            not offer, or no answer to a question without a default; the
            message names the question.
    """
    for name in answers:
        if name not in questions:
            raise ActionRefusedError(f"unknown question {name!r}")
    checked: dict[str, str] = {}
    for name, question in questions.items():
        answer = answers.get(name, question.default)
        if answer is None:
            choices = ", ".join(question.choices)
            raise ActionRefusedError(
                f"answer needed for {name!r}: {question.text}; choose {choices}"
            )
        if answer not in question.choices:
            choices = ", ".join(question.choices)
            raise ActionRefusedError(
                f"{answer!r} is not a choice for {name!r}; choose {choices}"
            )
        checked[name] = answer
    return checked
