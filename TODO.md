# TODO

- [ ] `RenameAction`: align with the same user-input coverage and validation as new-album (year/month/day/name semantics where applicable). Extract **shared** darkroom album folder-name construction + validation (used by `NewAlbumAction._execute` and `RenameAction._execute`, and keep GUI/dialog behavior consistent)
- [ ] `scan.py`: review silently skipping folders that do not match the recognized year/album patterns (extra dirs under darkroom or year are invisible today). Consider surfacing **ignored paths** (and optional reasons) as scan metadata or messages so a workflow/report can show what was not treated as an album
- [ ] add logging
- [ ] **Cull / edit commands:** replace ad-hoc shell-style parsing (`shlex.split(posix=False)` + stripping outer quotes) with something easier to reason about and harder to misconfigure—e.g. structured settings (executable path + argument list / template per arg), or a documented minimal parser—so we are not fighting Windows quoting and `shlex` semantics forever
- [ ] `layout.py` `_handle_execute_result`: not every action needs `rescan_and_refresh` after success (e.g. open, show); skip the scan when the action only launches a viewer or otherwise leaves the darkroom tree unchanged
