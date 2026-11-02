"""The ``darkroom`` (alias ``dr``) command-line tool over the core engine."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from photo_darkroom_manager.cli._app import run

__all__ = ["main", "run"]


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``darkroom`` and ``dr`` console scripts."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        # Pipes get UTF-8 whatever the locale, so agents can decode output.
        if stream.isatty():
            reconfigure(errors="replace")
        else:
            reconfigure(encoding="utf-8")
    return run(
        sys.argv[1:] if argv is None else argv,
        cwd=Path.cwd(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
