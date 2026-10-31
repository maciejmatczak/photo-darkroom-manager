# Legacy GUI (reference only)

The NiceGUI app as it was before the core split, parked here for reference
while the core and CLI are built (see `../ROADMAP.md`, Phases 2 and 4).

- Not source code: excluded from the package, ruff, ty and pytest. It is not
  kept working and will drift from the core; that is expected.
- `gui/` was `src/photo_darkroom_manager/gui/`; `tests/test_gui.py` was
  `tests/test_gui.py`. Imports still name the old modules
  (`manager.DarkroomManager`, `settings.Settings`).
- To run the original app, check out the commit before it moved here
  (`git log --follow docs/core-split/legacy-gui/gui/gui_app.py`).
- Phase 4 rebuilds a thin GUI over the engine, using this as the reference
  for its look and behaviour.
