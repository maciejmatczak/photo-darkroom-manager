# Tasks

## 1. Library constants

- [ ] 1.1 Move `PUBLISH_FOLDER`, `PHOTOS_FOLDER`, `VIDEOS_FOLDER` to new
      `library.py` and update every import (`models.py`, `actions.py`,
      `scan.py`, `gui/node.py`, tests); verify with
      `grep -rn "settings import .*_FOLDER" src tests` returning nothing and
      `uv run pytest` green.

## 2. User configuration service

- [ ] 2.1 Add `user_config.py` with `ConfigIssue` and `ConfigValues` (same
      fields and defaults as `Settings`, no folder-existence validators);
      verify `ConfigValues` accepts a path that does not exist.
- [ ] 2.2 Implement `UserConfig.load()` returning the problems found, with
      per-field validation, problems for read and parse errors and for
      missing and unknown keys, invalid raw values kept, and `exists`;
      verify with contract tests for every "Tolerant load" and "Invalid
      values are kept after load" scenario.
- [ ] 2.3 Define `ConfigValueError` and `UnknownConfigKeyError` in
      `user_config.py` and implement `get`, `get_valid` and `set` (dropping
      the key's problems on success); verify with contract tests for
      "Validated update of one value" and "Problems stay until fixed".
- [ ] 2.4 Implement `save()` writing YAML to the config path and returning
      it; verify with the "Round trip" and "Save while fixing" scenarios.
- [ ] 2.5 Add a contract test for "Configuration does not check the
      environment" (missing archive folder gives no load problem).

## 3. Engine

- [ ] 3.1 Rename `DarkroomManager` to `Engine` in new `engine.py`, delete
      `manager.py`; constructor takes an optional config path, creates
      `user_config` and loads it; update all imports in `src` and `tests`;
      verify `uv run pytest` green.
- [ ] 3.2 Add read-only properties `darkroom`, `showroom`, `archive`,
      `cull_command`, `edit_command` backed by `user_config.get_valid`, and
      switch engine methods to them; verify with the "Engine exposes the
      values it works with" scenario tests.
- [ ] 3.3 Implement derived `status` and `status_detail`; verify with
      contract tests for the "Engine status" and "Status detail" scenarios.
- [ ] 3.4 Define `EngineNotReadyError` in `engine.py` and make `rescan`,
      `rescan_subtree` and every action factory raise it unless `ready`;
      verify with the "Not ready rejects work" scenario test.
- [ ] 3.5 Add `log_level` and `set_log_level()`; configure logging with the
      default before loading, log load problems as warnings, then seed the
      level from env var, config, else `INFO`; verify with the "Runtime log
      level" scenario tests, an env-override test, and a test that a load
      problem is logged.

## 4. Remove the old settings API

- [ ] 4.1 Reduce `settings.py` to config-path and logs-dir discovery (or
      fold it into `user_config.py`), removing `Settings`,
      `load_settings`, `save_settings`; replace the `Settings` fixture in
      `tests/conftest.py` with an `Engine` over a temp config and temp
      roots; verify `grep -rn "load_settings\|save_settings" src tests`
      returns nothing.
- [ ] 4.2 Rewrite `tests/test_settings.py`: keep the path-discovery tests,
      drop the `internal` "invalid raises" tests now covered by the new
      contract tests; verify `uv run pytest -m internal` no longer lists
      them.

## 5. Parked GUI and verification

- [ ] 5.1 Rewire `gui/gui_app.py` and `gui/node.py` to the engine API per
      design.md (pre-filled settings page with `status_detail`, per-field
      set errors, save); verify `uv run pytest tests/test_gui.py` green and
      `uv run python -c "import photo_darkroom_manager.gui.gui_app"` works.
- [ ] 5.2 Full check: `uv run pytest`, `uv run ruff check`,
      `uv run ruff format --check` and `uv run ty check` all pass.
- [ ] 5.3 Update `docs/core-split/frontend-coupling.md` section 1 with a
      note that settings and startup are now core-owned, and check off the
      ROADMAP Phase 1 settings item.

## Workflow follow-up

- Archive the change with `/opsx:archive` after review, which creates
  `openspec/specs/engine/user-config` and `engine/engine-status`.
