"""Text and JSON renderings of core values: views, plans, results, status."""

from __future__ import annotations

import dataclasses
import itertools
import shlex
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    FileMove,
    MoveReport,
    Question,
    apps,
    archive,
    new_batch,
    publish,
    rename,
    tidy,
)
from photo_darkroom_manager.core.jobs import JobView
from photo_darkroom_manager.core.library import PHOTOS_FOLDER, FileCounts, NodeView
from photo_darkroom_manager.core.user_config import ConfigIssue

Data = dict[str, object]


def _counts_data(counts: FileCounts) -> Data:
    return {
        "images": counts.image_count,
        "videos": counts.video_count,
        "others": counts.other_file_count,
    }


def _counts_text(counts: FileCounts) -> str:
    return (
        f"{counts.image_count} images, {counts.video_count} videos, "
        f"{counts.other_file_count} other"
    )


def _shown_id(node_id: str) -> str:
    return node_id or "(root)"


# ---------------------------------------------------------------------------
# Node views
# ---------------------------------------------------------------------------


def view_data(view: NodeView, depth: int) -> Data:
    """A view with children down to *depth*; deeper levels only counted."""
    data: Data = {
        "id": view.id,
        "name": view.name,
        "kind": view.kind,
        "complete": view.complete,
        "files": _counts_data(view.stats),
        "total": _counts_data(view.total),
        "own_issues": sorted(view.own_issues),
        "issues": sorted(view.issues),
        "actions": sorted(view.actions),
        "child_count": len(view.children),
    }
    if depth > 0:
        data["children"] = [view_data(c, depth - 1) for c in view.children]
    return data


def view_text(view: NodeView, depth: int) -> str:
    lines = [
        f"{_shown_id(view.id)}  [{view.kind}]",
        f"  files here: {_counts_text(view.stats)}",
        f"  files total: {_counts_text(view.total)}",
    ]
    if view.issues:
        own = ", ".join(sorted(view.own_issues)) or "none"
        lines.append(f"  issues: {', '.join(sorted(view.issues))} (own: {own})")
    lines.append(f"  actions: {', '.join(sorted(view.actions))}")
    if not view.complete:
        lines.append("  incomplete: only the scanned part is shown")
    if view.children:
        lines.append("  children:")
        for child in view.children:
            _tree_lines(child, depth - 1, 2, lines)
    return "\n".join(lines)


def _tree_lines(view: NodeView, depth: int, indent: int, out: list[str]) -> None:
    pad = "  " * indent
    marks = "".join(f"  {issue}" for issue in sorted(view.issues))
    if not view.complete:
        marks += "  (incomplete)"
    out.append(f"{pad}{view.name}  [{view.kind}]  {_counts_text(view.total)}{marks}")
    if not view.children:
        return
    if depth > 0:
        for child in view.children:
            _tree_lines(child, depth - 1, indent + 1, out)
    else:
        out.append(f"{pad}  … {len(view.children)} more below")


# ---------------------------------------------------------------------------
# Plans and results
# ---------------------------------------------------------------------------


_RESULT_LIST_LINES = 35


def _capped(lines: Sequence[str]) -> list[str]:
    shown = [f"  {line}" for line in lines[:_RESULT_LIST_LINES]]
    if len(lines) > _RESULT_LIST_LINES:
        shown.append(f"  … and {len(lines) - _RESULT_LIST_LINES} more")
    return shown


# ---------------------------------------------------------------------------
# Typed action plans and results: one text and one JSON renderer per type
# ---------------------------------------------------------------------------


def _plain_data(value: object) -> object:
    """*value* as JSON data: paths as POSIX text, dataclasses as dicts."""
    if isinstance(value, Path):
        return value.as_posix()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _plain_data(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(k): _plain_data(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain_data(v) for v in value]
    return value


def _fields_data(value: object, *, skip: Sequence[str] = ()) -> Data:
    """Every field of a plan or result as JSON data, except *skip*."""
    assert dataclasses.is_dataclass(value) and not isinstance(value, type)
    return {
        f.name: _plain_data(getattr(value, f.name))
        for f in dataclasses.fields(value)
        if f.name not in skip
    }


def _questions_lines(questions: Mapping[str, Question]) -> list[str]:
    if not questions:
        return []
    lines = ["", "Decide before running:"]
    for name, question in questions.items():
        choices = ", ".join(question.choices)
        default = f"; default {question.default}" if question.default else ""
        lines.append(f"  {name}: {question.text} ({choices}{default})")
    return lines


def _move_lines(
    title: str,
    moves: Sequence[FileMove],
    bases: Sequence[Path],
    verb: str = "",
) -> list[str]:
    if not moves:
        return []
    prefix = f"{verb} " if verb else ""
    lines = [f"{title}: {len(moves)}"]
    lines += _capped(
        [
            f"{prefix}{_shown(m.source, bases)} → {_shown(m.target, bases)}"
            + (f" ({m.reason})" if m.reason and not verb else "")
            for m in moves
        ]
    )
    return lines


def _shown(path: Path, bases: Sequence[Path]) -> str:
    for base in bases:
        if path.is_relative_to(base) and path != base:
            return path.relative_to(base).as_posix()
    return str(path)


def _tidy_plan_text(plan: tidy.TidyPlan) -> list[str]:
    if plan.nothing_to_do:
        return ["Nothing to tidy", f"Folder: {plan.folder}"]
    photos = sum(1 for m in plan.moves if m.target.parent.name == PHOTOS_FOLDER)
    summary = f"Tidy {len(plan.moves)} files"
    if plan.conflicts:
        summary += f", {len(plan.conflicts)} conflict(s)"
    bases = [plan.folder]
    return [
        summary,
        f"Folder: {plan.folder}",
        f"Photos to move: {photos}",
        f"Videos to move: {len(plan.moves) - photos}",
        "",
        *_move_lines("Moves", plan.moves, bases, "move"),
        *_move_lines("Conflicts", plan.conflicts, bases),
    ]


def _archive_plan_text(plan: archive.ArchivePlan) -> list[str]:
    if plan.nothing_to_do:
        return ["Nothing to archive", f"Folder: {plan.source}"]
    summary = f"Archive {len(plan.moves)} files"
    if plan.conflicts:
        summary += f", {len(plan.conflicts)} already in the archive"
    bases = [plan.source, plan.source.resolve(), plan.target]
    return [
        summary,
        f"From: {plan.source}",
        f"To:   {plan.target}",
        "",
        *_move_lines("Moves", plan.moves, bases, "move"),
        *_move_lines("Already in the archive", plan.conflicts, bases),
    ]


def _publish_plan_text(plan: publish.PublishPlan) -> list[str]:
    if plan.nothing_to_do:
        return ["Nothing to publish: PUBLISH directory is empty"]
    files = len(plan.moves) + len(plan.replacements)
    summary = f"Publish {files} files"
    if plan.replacements:
        summary += f", {len(plan.replacements)} would be replaced"
    bases = [plan.publish_folder, plan.target]
    return [
        summary,
        f"From: {plan.publish_folder}",
        f"To:   {plan.target}",
        f"New: {len(plan.moves)}, already in the showroom: {len(plan.replacements)}",
        "",
        *_move_lines("Moves", plan.moves, bases, "move"),
        *_move_lines("Already in the showroom", plan.replacements, bases),
    ]


def _rename_plan_text(plan: rename.RenamePlan) -> list[str]:
    if plan.nothing_to_do:
        return [f"No change: {plan.folder.name}"]
    return [
        f"Rename {plan.folder.name} to {plan.new_folder.name}",
        f"Folder: {plan.folder.parent}",
    ]


def _new_batch_plan_text(plan: new_batch.NewBatchPlan) -> list[str]:
    created = plan.batch_folder.relative_to(plan.darkroom_root).as_posix()
    return [
        f"Create batch {created}",
        f"Darkroom: {plan.darkroom_root}",
        "",
        f"Folders to create: {len(plan.folders_to_create)}",
        *_capped([_shown(f, [plan.darkroom_root]) for f in plan.folders_to_create]),
    ]


_PLAN_TEXT: dict[type, Callable[[Any], list[str]]] = {
    tidy.TidyPlan: _tidy_plan_text,
    archive.ArchivePlan: _archive_plan_text,
    publish.PublishPlan: _publish_plan_text,
    rename.RenamePlan: _rename_plan_text,
    new_batch.NewBatchPlan: _new_batch_plan_text,
}
_PLAN_DATA: dict[type, Callable[[Any], Data]] = {
    plan_type: _fields_data for plan_type in _PLAN_TEXT
}


def action_plan_text(plan: ActionPlan, confirm: str | None) -> str:
    """A plan in its own terms, its questions, its fingerprint and how to run it."""
    lines = _PLAN_TEXT[type(plan)](plan)
    lines += _questions_lines(plan.questions)
    lines += ["", f"plan {plan.fingerprint}"]
    if confirm is not None:
        lines.append(f"run it: {confirm}")
    return "\n".join(lines)


def action_plan_data(
    action: str,
    node_id: str,
    plan: ActionPlan,
    confirm: Sequence[str] | None,
) -> Data:
    """A plan's own fields, with its action, node, questions and fingerprint."""
    return {
        "kind": "plan",
        "action": action,
        "node_id": node_id,
        **_PLAN_DATA[type(plan)](plan),
        "nothing_to_do": plan.nothing_to_do,
        "fingerprint": plan.fingerprint,
        "confirm": list(confirm) if confirm is not None else None,
    }


def _report_lines(report: MoveReport) -> list[str]:
    lines: list[str] = []
    if report.done:
        lines.append(f"done: {report.done} file(s)")
    if report.replaced:
        lines.append(f"replaced: {len(report.replaced)} file(s)")
    if report.failed:
        lines.append(f"failed: {len(report.failed)} file(s)")
        lines += _capped([f"{m.source}: {m.reason}" for m in report.failed])
    if report.skipped:
        lines.append(f"skipped: {len(report.skipped)} conflict(s)")
        lines += _capped([f"skip {m.source} ({m.reason})" for m in report.skipped])
    if report.left:
        lines.append(f"left: {len(report.left)} file(s)")
        lines += _capped([str(m.source) for m in report.left])
    return lines


def _moves_result_text(result: Any) -> list[str]:
    return _report_lines(result.moves)


def _archive_result_text(result: archive.ArchiveResult) -> list[str]:
    lines = _report_lines(result.moves)
    if result.remaining:
        lines.append(f"remaining: {len(result.remaining)} file(s)")
        lines += _capped([str(p) for p in result.remaining])
    if result.cleanup_problem:
        lines.append(result.cleanup_problem)
    return lines


def _rename_result_text(result: rename.RenameResult) -> list[str]:
    return [f"folder: {result.folder}"]


def _new_batch_result_text(result: new_batch.NewBatchResult) -> list[str]:
    return [f"created: {len(result.created)} folder(s)"]


def _open_folder_result_text(result: apps.OpenFolderResult) -> list[str]:
    return []


def _external_app_result_text(result: apps.ExternalAppResult) -> list[str]:
    return [f"command: {shlex.join(result.command)}"]


_RESULT_TEXT: dict[type, Callable[[Any], list[str]]] = {
    tidy.TidyResult: _moves_result_text,
    archive.ArchiveResult: _archive_result_text,
    publish.PublishResult: _moves_result_text,
    rename.RenameResult: _rename_result_text,
    new_batch.NewBatchResult: _new_batch_result_text,
    apps.OpenFolderResult: _open_folder_result_text,
    apps.ExternalAppResult: _external_app_result_text,
}
_RESULT_DATA: dict[type, Callable[[Any], Data]] = {
    result_type: _fields_data for result_type in _RESULT_TEXT
}


def action_result_text(result: ActionResult, node_id: str | None = None) -> str:
    """A result's outcome and message, then what it reports in its own terms."""
    lines = [f"{result.outcome}: {result.message}"]
    lines += _RESULT_TEXT[type(result)](result)
    if node_id is not None:
        lines.append(f"node: {_shown_id(node_id)}")
    return "\n".join(lines)


def action_result_data(
    action: str,
    result: ActionResult,
    node_id: str | None = None,
    library_refreshed: str | None = None,
) -> Data:
    """A result's own fields, with its action and what the engine added."""
    return {
        "kind": "result",
        "action": action,
        **_RESULT_DATA[type(result)](result),
        "node_id": node_id,
        "library_refreshed": library_refreshed,
    }


# ---------------------------------------------------------------------------
# Job progress
# ---------------------------------------------------------------------------


def progress_text(view: JobView, frame: str = "") -> str:
    """One line for a running job: a counter, or a spinner without a total."""
    what = str(view)
    progress = view.progress
    if progress.total is not None:
        count = f"{progress.done}/{progress.total}"
    else:
        count = f"{frame} {progress.done}".strip()
    line = f"{what}: {count}"
    if progress.current:
        line += f"  {progress.current}"
    if view.state == "cancelling":
        line += "  (cancelling)"
    return line


class Progress:
    """Redraws one progress line on a terminal stream."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._frames = itertools.cycle("|/-\\")
        self._width = 0

    def _write(self, text: str) -> None:
        text = text[:120]
        pad = max(self._width - len(text), 0)
        self._stream.write("\r" + text + " " * pad)
        self._stream.flush()
        self._width = len(text)

    def draw(self, view: JobView) -> None:
        self._write(progress_text(view, next(self._frames)))

    def note(self, text: str) -> None:
        self._write(text)

    def clear(self) -> None:
        if self._width:
            self._stream.write("\r" + " " * self._width + "\r")
            self._stream.flush()
            self._width = 0


# ---------------------------------------------------------------------------
# Status and configuration
# ---------------------------------------------------------------------------


def issues_data(issues: Sequence[ConfigIssue]) -> list[Data]:
    return [{"key": i.key, "message": i.message} for i in issues]


def issues_text(issues: Sequence[ConfigIssue]) -> list[str]:
    return [f"  {i.key}: {i.message}" for i in issues]


def value_text(value: object) -> str:
    return "" if value is None else str(value)


def value_data(value: object) -> object:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)
