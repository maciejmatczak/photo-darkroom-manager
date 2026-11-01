"""Library tree model: node facts by id, frozen views and the actions manifest."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from photo_darkroom_manager.core.library.layout import NodeKind

NodeId = str
"""Darkroom-relative POSIX path of a node; ``""`` is the root."""

NodeIssue = Literal["untidy"]


class NodeAction(StrEnum):
    """Operations the library allows on a folder of a given kind."""

    OPEN = "open"
    NEW_BATCH = "new_batch"
    RENAME = "rename"
    TIDY = "tidy"
    CULL = "cull"
    EDIT = "edit"
    PUBLISH = "publish"
    ARCHIVE = "archive"


_A = NodeAction
_ACTIONS: dict[NodeKind, frozenset[NodeAction]] = {
    "root": frozenset({_A.OPEN}),
    "device": frozenset({_A.OPEN, _A.NEW_BATCH}),
    "year": frozenset({_A.OPEN}),
    "batch": frozenset(
        {_A.OPEN, _A.RENAME, _A.TIDY, _A.CULL, _A.EDIT, _A.PUBLISH, _A.ARCHIVE}
    ),
    "publish": frozenset({_A.OPEN}),
    "subfolder": frozenset({_A.OPEN, _A.TIDY, _A.CULL, _A.EDIT, _A.ARCHIVE}),
}


def node_actions(kind: NodeKind) -> frozenset[NodeAction]:
    """Actions that apply to a node of *kind*, regardless of state or settings."""
    return _ACTIONS[kind]


def parent_id(node_id: NodeId) -> NodeId:
    """Id of the parent of *node_id*; the root's parent is the root."""
    return node_id.rpartition("/")[0]


def child_id(node_id: NodeId, name: str) -> NodeId:
    return f"{node_id}/{name}" if node_id else name


@dataclass(frozen=True, slots=True)
class FileCounts:
    image_count: int = 0
    video_count: int = 0
    other_file_count: int = 0

    def __add__(self, other: FileCounts) -> FileCounts:
        return FileCounts(
            self.image_count + other.image_count,
            self.video_count + other.video_count,
            self.other_file_count + other.other_file_count,
        )


@dataclass(frozen=True, slots=True)
class NodeFacts:
    """What a scan learns about one folder, without looking at its children."""

    kind: NodeKind
    stats: FileCounts
    """Files directly in the folder."""
    own_issues: frozenset[NodeIssue]
    children: tuple[NodeId, ...]


@dataclass(frozen=True, slots=True)
class NodeView:
    """Read-only snapshot of a node and its whole subtree."""

    id: NodeId
    name: str
    kind: NodeKind
    stats: FileCounts
    """Files directly in the folder."""
    total: FileCounts
    """Files in the whole subtree."""
    own_issues: frozenset[NodeIssue]
    issues: frozenset[NodeIssue]
    """Issues of the node and every descendant."""
    actions: frozenset[NodeAction]
    children: tuple[NodeView, ...]


@dataclass(frozen=True, slots=True)
class _Node:
    facts: NodeFacts
    total: FileCounts
    issues: frozenset[NodeIssue]


_Nodes = dict[NodeId, _Node]


class LibraryTree:
    """Scanned darkroom: node facts by id, with cached subtree totals.

    A model, not a service: it never reads the disk; callers scan and hand
    it facts. Updates build a new map and swap it in, so a view built while
    another thread replaces a subtree sees either the old or the new tree.
    """

    def __init__(self, root: Path, facts: Mapping[NodeId, NodeFacts]) -> None:
        if "" not in facts:
            raise ValueError("facts must contain the root id ''")
        self.root = root
        nodes: _Nodes = {}
        _insert(nodes, "", facts)
        self._nodes = nodes

    def contains(self, node_id: NodeId) -> bool:
        return node_id in self._nodes

    def kind(self, node_id: NodeId) -> NodeKind:
        return self._nodes[node_id].facts.kind

    def path(self, node_id: NodeId) -> Path:
        return self.root / node_id if node_id else self.root

    def nearest(self, node_id: NodeId) -> NodeId:
        """*node_id* if it is in the tree, else its closest indexed ancestor."""
        nodes = self._nodes
        while node_id and node_id not in nodes:
            node_id = parent_id(node_id)
        return node_id

    def view(self, node_id: NodeId) -> NodeView:
        """Build a frozen view of *node_id*'s subtree; ``KeyError`` if unknown."""
        return self._view(self._nodes, node_id)

    def replace_subtree(
        self, node_id: NodeId, facts: Mapping[NodeId, NodeFacts]
    ) -> None:
        """Swap *node_id*'s subtree for *facts* and update its ancestors.

        Ancestors are recomputed from stored facts; nothing is read from disk.
        """
        if node_id not in self._nodes:
            raise KeyError(node_id)
        if node_id not in facts:
            raise ValueError(f"facts must contain {node_id!r}")
        nodes = dict(self._nodes)
        _remove(nodes, node_id)
        _insert(nodes, node_id, facts)
        while node_id:
            node_id = parent_id(node_id)
            _aggregate(nodes, node_id, nodes[node_id].facts)
        self._nodes = nodes

    def _view(self, nodes: _Nodes, node_id: NodeId) -> NodeView:
        node = nodes[node_id]
        facts = node.facts
        return NodeView(
            id=node_id,
            name=node_id.rpartition("/")[2] if node_id else self.root.name,
            kind=facts.kind,
            stats=facts.stats,
            total=node.total,
            own_issues=facts.own_issues,
            issues=node.issues,
            actions=node_actions(facts.kind),
            children=tuple(self._view(nodes, c) for c in facts.children),
        )


def _remove(nodes: _Nodes, node_id: NodeId) -> None:
    node = nodes.pop(node_id)
    for child in node.facts.children:
        _remove(nodes, child)


def _insert(nodes: _Nodes, node_id: NodeId, facts: Mapping[NodeId, NodeFacts]) -> None:
    """Store *node_id*'s subtree from *facts*, totals bottom-up."""
    own = facts[node_id]
    for child in own.children:
        _insert(nodes, child, facts)
    _aggregate(nodes, node_id, own)


def _aggregate(nodes: _Nodes, node_id: NodeId, facts: NodeFacts) -> None:
    total = facts.stats
    issues = facts.own_issues
    for child in facts.children:
        child_node = nodes[child]
        total += child_node.total
        issues |= child_node.issues
    nodes[node_id] = _Node(facts, total, issues)
