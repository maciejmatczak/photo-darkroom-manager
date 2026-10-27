# Architecture Improvement Candidates

Deepening opportunities surfaced by `improve-codebase-architecture`. Each
candidate is described in terms of **locality** and **leverage** — see
`.agents/skills/improve-codebase-architecture/LANGUAGE.md` for vocabulary.

| # | Candidate | Status |
| --- | --- | --- |
| 1 | `scan` imports tidy detection from `actions` | Open |
| 2 | Manager path helpers fake a sum type | Partly done |
| 3 | Open-external discards its prepared command | Partly done |
| 4 | `file_utils` prune helpers tested via private import | Open |

---

## 1. `scan` imports tidy detection from `actions` — the read model depends on the write model

**Status**: Open.

**Files**: `src/photo_darkroom_manager/scan.py`,
`src/photo_darkroom_manager/actions.py`, `tests/actions/test_tidy.py`,
`tests/test_scan.py`

**Problem**: `scan.py` imports `collect_files_to_tidy` from `actions.py` to set
the `"untidy"` issue on batch nodes. This inverts the natural layer ordering:
the read-model module (building the `DarkroomNode` tree) depends on the
write-model module (which knows what `TidyAction` would move). "Is this folder
untidy?" — does it have photos not in `PHOTOS/` or videos not in `VIDEOS/`? —
is a domain predicate about batch folder conventions, not an action concern.
The `statistics` spec now relies on this predicate for issue roll-up, which
makes its placement more visible.

Two symptoms confirm the seam is in the wrong place:

- `test_tidy.py` imports `_collect_files_to_tidy` by its private underscore
  name to test this logic — callers are reaching _through_ the declared seam.
- `test_scan.py` imports `_detect_untidy` by its private underscore name.
  Deletion test: if you deleted `_detect_untidy` as a named function, its
  tests would break — it is earning its keep, but through the wrong seam.

**Solution**: Move `collect_files_to_tidy` (and its private helper
`_collect_files_to_tidy`) from `actions.py` into `media.py`, which already
owns the extension sets and `is_file_a_photo` / `is_file_a_video` predicates
they depend on. Both `scan.py` and `TidyAction` then import from `media.py`.
The `_detect_untidy` wrapper in `scan.py` reduces to an inline boolean and can
be deleted. Tests import from `media.py` publicly.

**Benefits**: Locality — tidy detection lives next to the media-type rules it
uses; change the convention in one place, nothing else needs to import from
`actions`. Leverage — the `media` module gains depth: it now encodes "which
files are misplaced under the batch folder convention" in addition to "what
type is this file?" The private-import brittleness in both test files
vanishes.

---

## 2. `DarkroomManager` path helpers use a runtime mutual-exclusion convention the type checker cannot verify

**Status**: Partly done. Path translation now lives in
`paths.translate_path(path, *, roots, from_area, to_area)`, where
`Area = Literal["darkroom", "archive", "showroom"]` is statically checked and
each area's layout is private to `paths.py`. The private `_translate_path` in
`manager.py` and its private-import tests are gone. The manager helpers below
remain.

**Files**: `src/photo_darkroom_manager/manager.py`, `tests/test_manager.py`

**Problem**: `darkroom_path(*, archive_path=None, showroom_path=None)`,
`showroom_path(*, ...)`, and `archive_path(*, ...)` each accept two
`Path | None` keyword arguments and enforce "exactly one non-None" via
`_require_one` at runtime. This fakes a sum type in Python's type system.
Callers must know the convention; passing zero arguments
(`manager.darkroom_path()`) is not a type error; and `_require_one` itself is
tested directly in `test_manager.py` because there is no narrower public seam
for the invariant. Each helper is now only a dispatch onto area translation,
so the three methods add interface without adding depth.

**Solution**: Replace the three mutual-exclusion methods with a single
`translate(path: Path, *, from_area: Area, to_area: Area) -> Path` method that
passes `self.settings` as the roots, or let callers use
`paths.translate_path` directly. `_require_one` and its tests disappear.
Callers in `gui/node.py` change from
`mgr.archive_path(darkroom_path=p)` to
`mgr.translate(p, from_area="darkroom", to_area="archive")`.

**Benefits**: Leverage — callers get a narrower, fully type-checkable
interface with no hidden runtime invariants. Locality — the constraint
"exactly one source area" becomes a type-checker responsibility, not a
runtime assertion repeated across three methods.

---

## 3. `OpenExternalAppAction` discards the prepared command

**Status**: Partly done. Rescan intent is solved: `ExecutionResult` carries an
optional `rescan_node_path`, actions that change the tree set it, and
`OpenExternalAppAction` leaves it `None`, so the GUI no longer rescans after
opening a viewer. The prepared-command half below remains.

**Files**: `src/photo_darkroom_manager/actions.py` (`OpenExternalAppAction`)

**Problem**: The `Action` template method's plan slot is `None` for
confirmation-free actions, hiding prepared state.
`OpenExternalAppAction._prepare` calls `_resolve_command` (which does
format-string substitution, filesystem lookup for `{first_image_in_folder}`,
and `shlex.split`) to validate the command template, then returns `None`.
`_execute` re-invokes `_resolve_command` identically. The resolved
`parts: list[str]` — the only real output of preparation — is thrown away
between the two steps. If `{first_image_in_folder}` disappears between prepare
and execute, the two invocations diverge silently.

**Solution**: Add `OpenExternalAppPlan(parts: list[str])` as the concrete plan
type. `_prepare` returns it; `_execute` uses `plan.parts`, calling
`_resolve_command` exactly once. Check how the GUI's `run_action` treats a
non-`None` plan first: today a plan triggers the review dialog, so the plan
type needs a way to skip confirmation.

**Benefits**: `OpenExternalAppAction` gains depth: its plan carries real state
(`parts`) instead of `None`, and the command is resolved at most once per
action lifecycle.

---

## 4. `file_utils` prune helpers tested via private import — the seam is below the public interface

**Status**: Open.

**Files**: `src/photo_darkroom_manager/file_utils.py`,
`tests/file_utils/test_prune.py`

**Problem**: `test_prune.py` imports `_prune_empty_dirs_under` and
`_rmdir_empty_dir` via their underscore-private names. `file_utils.py` is
already a deep module — `merge_tree_into_archive` and
`preview_merge_into_archive` hide substantial behaviour behind a clean
interface. The prune helpers are its internal seam. Deletion test applied to
`_prune_empty_dirs_under`: several tests fail, so it is earning its keep. But
the test surface crosses below the declared interface, making these tests
brittle to any internal restructuring of `file_utils`.

The choice is between two directions: (a) promote the helpers to public —
appropriate if their contract is stable and independently useful beyond
`merge_tree_into_archive`; (b) collapse the tests into `test_merge.py`,
verifying prune behaviour through the outcome of `merge_tree_into_archive` —
appropriate if the helpers are genuinely implementation details. Currently the
tests do both: `test_merge.py` covers the merge outcome and `test_prune.py`
covers the pruning mechanics. The interface is effectively split.

**Solution**: Decide one direction and commit to it. If the prune logic is
independently useful, drop the underscores and document the contracts. A
likely second caller exists: the TODO item about empty `DEVICE/YEAR/` folders
left after archiving a whole batch could reuse it. If not, remove
`test_prune.py`, add an assertion about empty-directory pruning to
`test_merge.py`, and keep the helpers private.

**Benefits**: Either way — leverage if promoted (callers get a named, tested
capability); locality if collapsed (all `file_utils` behaviour verified
through one seam, restructuring the internals is free).
