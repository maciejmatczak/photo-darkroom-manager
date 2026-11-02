"""Turn a TARGET argument into a node id: ``id:`` ids, paths, bare names.

This is input syntax only; which node a path or id names is the engine's
answer (``library_resolve``) and the request guard's.
"""

from __future__ import annotations

from pathlib import Path

from photo_darkroom_manager.core.engine import (
    Engine,
    EngineNotReadyError,
    PathOutsideDarkroomError,
)
from photo_darkroom_manager.core.library import (
    NodeId,
    canonical_id,
    is_well_formed_id,
)

ID_PREFIX = "id:"


class AmbiguousTargetError(ValueError):
    """A bare target names one node as an id and another as a path."""

    def __init__(self, text: str, as_id: NodeId, as_path: NodeId) -> None:
        super().__init__(f"{text!r} names two nodes: id {as_id!r} and path {as_path!r}")
        self.text = text
        self.as_id = as_id
        self.as_path = as_path


def resolve(text: str, cwd: Path, engine: Engine) -> NodeId:
    """Node id for *text*, read as an ``id:`` id, a path, or a bare target.

    An absolute path, or one starting with ``.``, is a path relative to
    *cwd*. Bare text counts as a path when that folder exists inside the
    darkroom, and as an id when its folder exists; one that names neither
    is kept as an id so the engine's guard can answer (or create it).
    """
    if text.startswith(ID_PREFIX):
        return text[len(ID_PREFIX) :]
    if text == "":
        return ""
    path = Path(text)
    if path.is_absolute() or text.startswith("."):
        return engine.library_resolve(cwd / path)
    return _bare(text, cwd / path, engine)


def default_target(cwd: Path, engine: Engine) -> NodeId:
    """The node at *cwd* when it is in the darkroom, else the root."""
    try:
        return engine.library_resolve(cwd)
    except PathOutsideDarkroomError:
        return ""


def _bare(text: str, candidate: Path, engine: Engine) -> NodeId:
    darkroom = engine.darkroom
    if engine.status != "ready" or darkroom is None:
        raise EngineNotReadyError(engine.status, engine.status_detail)

    as_path: NodeId | None = None
    if candidate.is_dir():
        try:
            as_path = engine.library_resolve(candidate)
        except PathOutsideDarkroomError:
            as_path = None

    as_id = text.replace("\\", "/").strip("/")
    as_id_counts = False
    if is_well_formed_id(as_id):
        as_id = canonical_id(darkroom, as_id)
        as_id_counts = (darkroom / as_id).is_dir()

    if as_path is not None and as_id_counts and as_path != as_id:
        raise AmbiguousTargetError(text, as_id, as_path)
    if as_path is not None:
        return as_path
    return as_id
