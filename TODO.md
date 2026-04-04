# TODO

- [ ] add type checker (ty vs?...)
- [ ] implement tests
- [ ] add support for opening external applications (e.g. for culling, for editing)
- [ ] add logging
- [ ] `ArchiveAction._prepare` should not create directories (side-effect in prepare step); move `target_dir.parent.mkdir(...)` to `_execute` instead
- [ ] `DarkroomYearAlbum` / `validate_album`: validate month is `01`–`12` (reject e.g. `2024-13`); see `test_darkroom_year_album_permissive_regex_accepts_non_calendar_month` TODO in tests
- [ ] `DarkroomYearAlbum` / `validate_album`: require a real `YYYY-MM` album prefix (e.g. word boundary or `-` + optional space before the rest); reject glued suffixes like `2024-01foo`; see `test_darkroom_year_album_permissive_regex_accepts_tight_prefix` TODO in tests
