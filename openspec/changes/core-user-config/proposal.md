# Proposal

## Why

Loading the configuration today is all or nothing: one invalid field, or one
library root that is not reachable, rejects the whole file. The GUI swallows
the error, shows "not configured" and opens an empty settings form, so the user
loses every value and never learns what was wrong. Settings are also built,
saved and applied (logging) by the GUI rather than the core. This is the first
Phase 1 step of the `dev-core-split` roadmap: the core must own user
configuration before a CLI can sit on top of it.

## What Changes

- New user configuration service, `engine.user_config`, the single source
  of truth for configured values:
  - `load()` never fails on bad or unreadable content; valid fields load,
    and it returns the problems found, each naming its key (also kept as
    `issues` until fixed).
  - `get(key)` and `set(key, value)`; `set` rejects an invalid value with a
    typed `ConfigValueError`, and a stored value is in effect at once.
  - `save()` writes the file explicitly, also while problems remain.
- New engine state, with nothing to apply or keep in sync:
  - Read-only properties for the values the engine works with (`darkroom`,
    `showroom`, `archive`, `cull_command`, `edit_command`), each reading
    from `user_config` today.
  - `engine.status` (`unconfigured`, `invalid`, `ready`) and
    `engine.status_detail`, derived on read from the configuration and the
    disk; scans and actions are rejected unless `ready`.
  - `engine.log_level` as runtime state: seeded from the configuration when
    the engine starts, then managed by the engine only.
- Folder-existence checks move out of configuration validation into the
  engine status. **BREAKING** (internal API): `Settings`,
  `load_settings()` and `save_settings()` are replaced by the service.
- Library folder conventions (`PUBLISH`, `PHOTOS`, `VIDEOS`) move from
  `settings.py` to the library domain module. **BREAKING** (internal
  imports only).
- Typed exceptions for single-value commands, defined in the module that
  raises them (`ConfigValueError` in the user configuration module).

Non-goals: partial operation (the engine is either ready or not), a schema
or layered configuration system, change notifications, the CLI itself, and
rewiring the parked GUI beyond keeping it importable.

## Capabilities

### New Capabilities

- `engine/user-config`: loading, reading, updating and saving the user's
  configuration, and how configuration problems are reported to clients.
- `engine/engine-status`: the configuration-backed values the engine
  exposes, whether it can work and why not, and runtime state such as the
  log level that is separate from the user's configuration.

### Modified Capabilities

None. `app/library-layout` keeps its "three configured roots" requirement;
how roots are configured is not specified there.

## Impact

- Code: `settings.py` (split into user config and library constants),
  `manager.py` (becomes `engine.py` with `user_config`, properties, status,
  log level), `logging_config.py` (driven by the engine),
  `gui/gui_app.py` and `gui/node.py` (minimal rewiring; GUI is parked), a
  new `library.py` (folder constants), and every module importing them.
- Tests: `tests/test_settings.py` "invalid raises" tests (marked
  `internal`) are replaced; new contract tests for load, set, save, status
  and log level.
- No new dependencies; config file format (YAML keys) stays the same.
