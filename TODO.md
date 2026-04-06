# TODO

- [ ] add type checker (ty vs?...)
- [ ] implement tests
- [ ] add support for opening external applications (e.g. for culling, for editing)
- [ ] add logging
- [ ] `ArchiveAction._prepare` should not create directories (side-effect in prepare step); move `target_dir.parent.mkdir(...)` to `_execute` instead
- [ ] `DarkroomYearAlbum` / `validate_album`: validate month is `01`–`12` (reject e.g. `2024-13`); see `test_darkroom_year_album_permissive_regex_accepts_non_calendar_month` TODO in tests
- [ ] `DarkroomYearAlbum` / `validate_album`: require a real `YYYY-MM` album prefix (e.g. word boundary or `-` + optional space before the rest); reject glued suffixes like `2024-01foo`; see `test_darkroom_year_album_permissive_regex_accepts_tight_prefix` TODO in tests
- [ ] `NewAlbumAction` / `DarkroomManager.new_album_action`: accept `name: str | None` (not only `str`); treat `None` like “no title” in `_execute` (same folder naming as `""` today). Update GUI (`layout.py` `_show_new_album_dialog`: pass `None` when the optional name field is blank instead of `""`) and any other callers
- [ ] `RenameAction`: align with the same user-input coverage and validation as new-album (year/month/day/name semantics where applicable). Extract **shared** darkroom album folder-name construction + validation (used by `NewAlbumAction._execute` and `RenameAction._execute`, and keep GUI/dialog behavior consistent)
- [ ] `scan.py`: review silently skipping folders that do not match the recognized year/album patterns (extra dirs under darkroom or year are invisible today). Consider surfacing **ignored paths** (and optional reasons) as scan metadata or messages so a workflow/report can show what was not treated as an album
