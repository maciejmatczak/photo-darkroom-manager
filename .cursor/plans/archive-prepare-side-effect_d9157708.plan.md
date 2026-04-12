---
name: archive-prepare-side-effect
overview: Remove filesystem side effects from archive preparation by moving directory creation from `ArchiveAction._prepare` into `ArchiveAction._execute`, and add regression coverage for this behavior.
todos:
  - id: remove-prepare-side-effect
    content: Remove directory creation from `ArchiveAction._prepare` and add it to `_execute` before merge.
    status: completed
  - id: add-regression-test
    content: Add a test that asserts `_prepare()` does not create archive destination directories.
    status: completed
  - id: run-required-checks
    content: Run formatting, lint autofix, typing, and archive action tests to verify behavior.
    status: completed
isProject: false
---

# Move Archive mkdir to Execute

## Scope
Implement the TODO item in [d:\workspace\photo-darkroom-manager\TODO.md](d:\workspace\photo-darkroom-manager\TODO.md): keep `ArchiveAction._prepare` side-effect-free by moving `target_dir.parent.mkdir(...)` into execute-time behavior.

## Planned Changes
- Update [d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\actions.py](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\actions.py):
  - In `ArchiveAction._prepare`, remove `target_dir.parent.mkdir(parents=True, exist_ok=True)`.
  - In `ArchiveAction._execute`, create the destination parent directory before `merge_tree_into_archive(...)` using `plan.target_dir.parent.mkdir(parents=True, exist_ok=True)`.
- Add/extend tests in [d:\workspace\photo-darkroom-manager\tests\actions\test_archive.py](d:\workspace\photo-darkroom-manager\tests\actions\test_archive.py):
  - New regression test: `_prepare()` should not create archive destination directories.
  - Keep existing execute-path assertions; ensure successful execute still materializes destination files.

## Validation
- Run required checks in workspace order:
  - `uv run ruff format`
  - `uv run ruff check --fix`
  - `uv run ty check`
- Run focused tests for archive action behavior (at minimum `tests/actions/test_archive.py`).

## Notes
Current code creates directories in `_prepare` while computing `target_dir`; this plan shifts all archive-dir creation to confirmed execution so canceling after prepare does not mutate the filesystem.
