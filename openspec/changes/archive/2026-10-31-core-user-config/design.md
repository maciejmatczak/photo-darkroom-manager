# Design

## Context

- `settings.py` holds one pydantic `Settings` model (three root paths, two
  optional commands, log level), config-path discovery, `load_settings()` /
  `save_settings()`, and the library folder constants `PUBLISH_FOLDER`,
  `PHOTOS_FOLDER`, `VIDEOS_FOLDER` (imported by `models.py`, `actions.py`,
  `scan.py` and `gui/node.py`).
- The root validators check that each folder exists, so an unplugged drive
  makes the whole file invalid. `load_settings()` raises on any problem;
  `gui_app` swallows it without logging, and logging is configured only after
  a successful load.
- `DarkroomManager(settings)` receives a finished `Settings`; the GUI calls
  `configure_logging()` itself, which already re-applies the level on repeat
  calls. The `PHOTO_DARKROOM_MANAGER_LOG_LEVEL` env var overrides the level.
- The core has no domain exception classes today: validators raise
  `ValueError`, and actions turn failures into `PrepareError` values.
- The GUI is to be parked on this branch (ROADMAP Phase 2); `tests/test_gui.py`
  is marked `internal`.

## Goals / Non-Goals

**Goals:**

- The usage this change makes possible:

  ```python
  engine = Engine()                        # loads config, seeds log level
  issues = engine.user_config.load()       # reload -> list[ConfigIssue]
  engine.user_config.issues                # same, kept until fixed
  engine.user_config.get("archive")        # raw or validated value
  engine.user_config.set("archive", p)     # raises ConfigValueError
  engine.user_config.save()                # -> Path

  engine.archive                           # Path | None, read-only
  engine.status                            # "unconfigured"|"invalid"|"ready"
  engine.status_detail                     # str | None
  engine.log_level; engine.set_log_level("DEBUG")
  ```

- Contract tests for every scenario in the two spec deltas.

**Non-Goals:**

- Partial operation, per-capability health, change events.
- A configuration schema framework or layered sources beyond the existing
  env override.
- What triggers a runtime log-level change (CLI flag, dashboard): later.
- The CLI; redesigning the GUI settings page.

## Decisions

### `DarkroomManager` becomes `Engine`

Rename the class to `Engine` in a new `engine.py` and remove `manager.py`.
The constructor takes an optional config path instead of a `Settings`
object. Existing methods (rescan, action factories, path helpers,
`list_devices`) move unchanged apart from reading roots from the engine's
own properties. Alternative: keep `DarkroomManager` and add the new API;
rejected because the roadmap already names this facade the engine and the
rename is mechanical now, costly later.

### One source of truth: `user_config`, exposed through engine properties

Configured values live only in `engine.user_config`. The engine exposes the
values it works with as read-only properties whose body today is just a
read from the service:

```python
@property
def archive(self) -> Path | None:
    return self.user_config.get_valid("archive")
```

Engine code reads `self.archive`, never `user_config` directly, so each
property is the one seam to change if a value later needs another source
(runtime override, CLI flag, per-job value). Writes go only through
`user_config.set`. Alternatives considered:

- The engine keeps its own copy, filled by an `apply_config()` step and
  written back on change. Rejected: two copies plus sync code per field,
  and every change must decide whether it also saves.
- Engine code reads `user_config` directly everywhere. Rejected: no seam,
  and the engine's working state is not visible on its interface.

`get(key)` returns what is stored, including an invalid raw value from the
file (for forms); `get_valid(key)` returns `None` when the key is missing or
has a problem, which is what the engine properties use.

### `UserConfig` over a raw dict with per-field validation

`UserConfig` (`user_config.py`) holds `_raw: dict[str, object]` as read
from YAML (invalid values kept), `_issues: dict[str, list[ConfigIssue]]`,
`exists: bool`, and a field table derived from one pydantic model,
`ConfigValues`, with today's fields and defaults but no folder-existence
validators.

- `load()` reads the file. Missing file: `exists = False`, no values, no
  issues. Read (`OSError`) or YAML parse error: one issue with key `"*"`.
  Otherwise each known field is validated on its own with a pydantic
  `TypeAdapter`; missing required keys and unknown keys become issues. It
  replaces previous issues and returns the flat list.
- `set(key, value)` validates the same way; on success stores the value and
  drops that key's issues, else raises.
- `save()` writes `_raw` to YAML (validated values serialized with
  `model_dump(mode="json")` semantics) and returns the path.

Per-field validation keeps the valid parts of a broken file, which
whole-model validation cannot. Issues are the service's own state, cleared
by its own operations, so nothing outside it has to stay in sync.

### Derived status and detail

`status` and `status_detail` are properties computed on every read:

- `unconfigured`: `not user_config.exists`;
- `invalid`: any `user_config.issues`, or a root that does not exist or is
  not a folder (three `stat` calls);
- `ready`: otherwise; `status_detail` is `None`.

`status_detail` joins every reason as `"<key>: <message>"`. Nothing is
stored, so nothing needs clearing: fixing a value or plugging in a drive
changes the status on the next read. Alternative: an `engine.issues` list
set by an apply step; rejected because it is extra state with unclear
ownership and clearing rules.

`rescan`, `rescan_subtree` and every action factory call
`_require_ready()`, raising `EngineNotReadyError(status, detail)`.

### Roots reach actions as explicit arguments

The engine's root properties are `Path | None`; they are defined whenever
the status is `ready`. Each factory checks readiness, then passes the roots
an action uses as explicit arguments (`ArchiveAction(folder, darkroom=...,
archive=...)`); `translate_path` takes `from_root` and `to_root` the same
way. There is no roots type between the engine and the actions.

Actions do not assume the engine validated anything: each one checks that
its roots are folders in `prepare` and again in `execute`, and refuses with
a `PrepareError` or failed result naming the root. The engine check stays
the early one, since it can report every reason through `status_detail`;
the action check is what keeps a stale action from touching files after a
drive goes away. Alternatives: the engine runs actions through
`engine.prepare/execute` gates (rejected: actions would rely on a caller
convention), or factories inject a readiness callback into each action
(rejected: couples actions back to the engine).

### Exceptions live with their interface

Exceptions are part of the interface of the module that raises them:

- `user_config.py`: `ConfigValueError(key, message)` (subclasses
  `ValueError`) and `UnknownConfigKeyError(key)` (subclasses `KeyError`).
- `engine.py`: `EngineNotReadyError(status, detail)`.

Alternative: a shared `errors.py` with a `DarkroomError` base; rejected
because it pulls each domain's interface out of its module and couples
unrelated domains through one file.

### Runtime log level

`Engine.__init__` configures logging with the default level first, so
problems found while loading reach the log, then calls `user_config.load()`
and logs each problem as a warning. It then seeds `self.log_level` from the
env var (ignored with a warning if invalid), else the configuration's valid
log level, else `INFO`, and reapplies it with `configure_logging`. The env
override is read by the engine, not by `logging_config`. From then on the log level is engine
state: `set_log_level(level)` validates, updates the attribute and
reconfigures logging, and never touches `user_config`; configuration edits
do not change it. Persisting a new default is a separate, explicit
`user_config.set("log_level", ...)` plus `save()`.

### Library constants

Move `PUBLISH_FOLDER`, `PHOTOS_FOLDER`, `VIDEOS_FOLDER` to a new
`library.py` (library layout conventions); `models.py` imports them, so a
small dedicated module avoids import cycles through `media.py`.
`settings.py` is deleted (see below).

### The engine owns application paths

Where the config file and the logs live is application knowledge, so the
engine owns it: `engine.py` holds `APP_NAME`, the env var names,
`default_config_path()` and `default_logs_dir()`.
`Engine(config_path=None, logs_dir=None)` uses them only when no path is
given. The services stay self-contained: `UserConfig(path)` loads and saves
only the path it is given, and `configure_logging(level, logs_dir=...)`
neither discovers directories nor reads env vars. Alternatives: keep a
`settings.py` discovery module (rejected: a central module every domain
reaches into for app-level names), or let `UserConfig` find its own default
path (rejected: puts application policy into the service).

### Parked GUI

The GUI is not adapted. It moves unchanged, with its tests, to
`docs/core-split/legacy-gui/` as reference material for ROADMAP Phase 4: excluded
from the package, ruff, ty and pytest, and allowed to drift. The GUI
console scripts are removed; there is no runnable client until the CLI.
Alternatives: minimal rewiring per change (rejected: parking means not
touching it); deleting it and pointing at a tag (rejected: harder to
consult while designing the new clients).

## Risks / Trade-offs

- Values can change between two reads within one operation → acceptable
  with one client and no jobs; a job will take a copy when it starts.
- Status re-checks the disk on every read → three `stat` calls; cache only
  if profiling shows a need.
- Per-field validation drops cross-field checks → none exist today; add
  them as issues at load and set when needed.
- Saving with problems writes invalid raw values back → intended, so a
  half-fixed file is never lost; load reports them again.
- Renaming `DarkroomManager` touches many tests → mechanical; one task with
  the suite as the check.
