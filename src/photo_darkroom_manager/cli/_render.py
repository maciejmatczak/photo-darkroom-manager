"""Text and JSON renderings of core values: views, plans, results, status."""

from __future__ import annotations

from collections.abc import Sequence

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ExecutionResult,
    Step,
    describe_step,
)
from photo_darkroom_manager.core.library import FileCounts, NodeView
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


def plan_data(plan: ActionPlan, confirm: Sequence[str]) -> Data:
    request = plan.request
    return {
        "kind": "plan",
        "request": {
            "action": str(request.action),
            "node_id": request.node_id,
            "params": dict(request.params),
        },
        "summary": plan.summary,
        "notes": list(plan.notes),
        "changes_files": plan.changes_files,
        "fingerprint": plan.fingerprint,
        "steps": [step.as_dict() for step in plan.steps],
        "confirm": list(confirm),
    }


def plan_text(plan: ActionPlan, confirm: str) -> str:
    return "\n".join(
        [
            plan.preview_text(),
            "",
            f"plan {plan.fingerprint}",
            f"run it: {confirm}",
        ]
    )


def _step_data(step: Step) -> Data:
    return step.as_dict()


def result_data(result: ExecutionResult) -> Data:
    return {
        "kind": "result",
        "outcome": result.outcome,
        "message": result.message,
        "details": result.details,
        "done": [_step_data(s) for s in result.done],
        "failed": [
            {"step": _step_data(f.step), "reason": f.reason} for f in result.failed
        ],
        "left": [p.as_posix() for p in result.left],
        "fingerprint": result.fingerprint,
        "node_id": result.node_id,
        "library_refreshed": result.library_refreshed,
    }


def result_text(result: ExecutionResult) -> str:
    lines = [f"{result.outcome}: {result.message}"]
    if result.done:
        lines.append(f"done: {len(result.done)} step(s)")
    if result.failed:
        lines.append(f"failed: {len(result.failed)} step(s)")
        lines.extend(f"  {describe_step(f.step)}: {f.reason}" for f in result.failed)
    if result.left:
        lines.append(f"left: {len(result.left)} file(s)")
        lines.extend(f"  {p}" for p in result.left)
    if result.details and not result.failed:
        lines.append(result.details)
    if result.node_id is not None:
        lines.append(f"node: {_shown_id(result.node_id)}")
    return "\n".join(lines)


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
