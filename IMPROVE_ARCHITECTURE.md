# Architecture Improvement Candidates

Deepening opportunities surfaced by `improve-codebase-architecture`. Each candidate is described in terms of **locality** and **leverage** — see `.agents/skills/improve-codebase-architecture/LANGUAGE.md` for vocabulary.

---

## 1. `scan` imports tidy-detection from `actions` — the read model depends on the write model

**Files**: `src/photo_darkroom_manager/scan.py`, `src/photo_darkroom_manager/actions.py`, `tests/actions/test_tidy.py`, `tests/test_scan.py`

**Problem**: `scan.py` imports `collect_files_to_tidy` from `actions.py` to set the `"untidy"` issue on album nodes. This inverts the natural layer ordering: the read-model module (building the `DarkroomNode` tree) depends on the write-model module (which knows what `TidyAction` would move). "Is this folder untidy?" — does it have photos not in `PHOTOS/` or videos not in `VIDEOS/`? — is a domain predicate about album folder conventions, not an action concern.

Two symptoms confirm the seam is in the wrong place:
- `test_tidy.py` imports `_collect_files_to_tidy` by its private underscore name to test this logic — callers are reaching _through_ the declared seam.
- `test_scan.py` imports `_detect_untidy` by its private underscore name. Deletion test: if you deleted `_detect_untidy` as a named function, its two tests would break — it is earning its keep, but through the wrong seam.

**Solution**: Move `collect_files_to_tidy` (and its private helper `_collect_files_to_tidy`) from `actions.py` into `media.py`, which already owns the extension sets and `is_file_a_photo` / `is_file_a_video` predicates they depend on. Both `scan.py` and `TidyAction` then import from `media.py`. The `_detect_untidy` wrapper in `scan.py` reduces to an inline boolean and can be deleted. Tests import from `media.py` publicly.

**Benefits**: Locality — tidy-detection lives next to the media-type rules it uses; change the convention in one place, nothing else needs to import from `actions`. Leverage — the `media` module gains depth: it now encodes "which files are misplaced under the Darkroom folder convention" in addition to "what type is this file?" The private-import brittleness in both test files vanishes.

---

## 2. `DarkroomManager` path-translation uses a runtime mutual-exclusion convention the type checker cannot verify

**Files**: `src/photo_darkroom_manager/manager.py`, `tests/test_manager.py`

**Problem**: `darkroom_path(*, archive_path=None, showroom_path=None)`, `showroom_path(*, ...)`, and `archive_path(*, ...)` each accept two `Path | None` keyword arguments and enforce "exactly one non-None" via `_require_one` at runtime. This fakes a sum type in Python's type system. The interface is nearly as complex as the implementation: callers must know the convention; passing zero arguments (`manager.darkroom_path()`) is not a type error; and `_require_one` itself is tested directly (lines 34–43 in `test_manager.py`) because there is no narrower public seam for the invariant. `_translate_path` is also tested via its private name — it is doing real work (deletion test: four tests break if it disappears) but is accessed below the declared seam.

**Solution**: Replace the three mutual-exclusion methods with a single `translate(path: Path, *, from_root: Literal["darkroom", "showroom", "archive"], to_root: Literal["darkroom", "showroom", "archive"]) -> Path` method. The `Literal` type makes the constraint statically checkable. `_require_one` disappears; `_translate_path` is either promoted to a public helper or inlined into the single method. The private-import tests in `test_manager.py` become redundant.

**Benefits**: Leverage — callers get a narrower, fully type-checkable interface with no hidden runtime invariants. The private-import brittleness in `test_manager.py` is eliminated. Locality — the constraint "exactly one root pair" becomes a type-checker responsibility, not a runtime assertion scattered across three methods.

---

## 3. `OpenExternalAppAction` discards the prepared command, and `ExecutionResult` carries no rescan intent

**Files**: `src/photo_darkroom_manager/actions.py` (`OpenExternalAppAction`, `ExecutionResult`), `src/photo_darkroom_manager/gui/layout.py` (`_handle_execute_result`)

**Problem**: Two related issues with the same root cause — the `Action` template method's plan slot is `None` for confirmation-free actions, hiding prepared state.

First: `OpenExternalAppAction._prepare` calls `_resolve_command` (which does format-string substitution, filesystem lookup for `{first_image_in_folder}`, and `shlex.split`) to validate the command template, then returns `None`. `_execute` re-invokes `_resolve_command` identically. The resolved `parts: list[str]` — the only real output of preparation — is thrown away between the two steps. If `{first_image_in_folder}` disappears between prepare and execute, the two invocations diverge silently.

Second: `_handle_execute_result` in `layout.py` unconditionally calls `rescan_and_refresh()` after every successful execute. But `OpenExternalAppAction` just opens a viewer and leaves the Darkroom tree unchanged. TODO.md flags this as a known bug. The decision "does this action require a rescan?" belongs to the action that knows what it did — not to the GUI layer that does not.

**Solution**: Add `OpenExternalAppPlan(parts: list[str])` as the concrete plan type. `_prepare` returns it; `_execute` uses `plan.parts`, calling `_resolve_command` exactly once. Separately, add a `requires_rescan: bool = True` field to `ExecutionResult`. `OpenExternalAppAction._execute` returns `ExecutionResult(..., requires_rescan=False)`. `_handle_execute_result` checks `result.requires_rescan` before triggering a rescan.

**Benefits**: Locality — the knowledge "this action does not mutate the Darkroom tree" moves from the GUI into the action that has the evidence. The unnecessary-rescan bug is fixed in one domain declaration rather than a GUI guard. `OpenExternalAppAction` gains depth: its plan carries real state (`parts`) instead of `None`, and the command is resolved at most once per action lifecycle.

---

## 4. `file_utils` prune helpers tested via private import — the seam is below the public interface

**Files**: `src/photo_darkroom_manager/file_utils.py`, `tests/file_utils/test_prune.py`

**Problem**: `test_prune.py` imports `_prune_empty_dirs_under` and `_rmdir_empty_dir` via their underscore-private names. `file_utils.py` is already a deep module — `merge_tree_into_archive` and `preview_merge_into_archive` hide substantial behaviour behind a clean interface. The prune helpers are its internal seam. Deletion test applied to `_prune_empty_dirs_under`: four tests fail, so it is earning its keep. But the test surface crosses below the declared interface, making these tests brittle to any internal restructuring of `file_utils`.

The choice is between two directions: (a) promote the helpers to public — appropriate if their contract is stable and independently useful beyond `merge_tree_into_archive`; (b) collapse the tests into `test_merge.py`, verifying prune behaviour through the outcome of `merge_tree_into_archive` — appropriate if the helpers are genuinely implementation details. Currently the tests do both: `test_merge.py` covers the merge outcome and `test_prune.py` covers the pruning mechanics. The interface is effectively split.

**Solution**: Decide one direction and commit to it. If the prune logic is independently useful (e.g., a caller might want to prune empty directories without a full archive merge), drop the underscores and document the contracts. If not, remove `test_prune.py`, add an assertion about empty-directory pruning to `test_merge.py`, and keep the helpers private.

**Benefits**: Either way — leverage if promoted (callers get a named, tested capability); locality if collapsed (all `file_utils` behaviour verified through one seam, restructuring the internals is free).
