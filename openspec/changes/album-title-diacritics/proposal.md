## Why

Album folders with diacritic characters in their titles (e.g., `2026-03 été`,
`2025-08 Wiosna ą`, `2024-12 München`) are rejected by the model validation
layer, making them impossible to Publish, Archive, or Rename. The
`_TITLE_ALLOWED` regex in `models.py` is ASCII-only, which is an arbitrary
restriction for an app that runs in any locale. Additionally, `scan.py` has its
own independent definition of "what is a valid album folder" (`ALBUM_PATTERN`),
creating two sources of truth that can drift apart.

## What Changes

- Widen `_TITLE_ALLOWED` in `models.py` from ASCII-only
  (`[a-zA-Z0-9_\- ]`) to Unicode word characters (`[\w\- ]` with
  `re.UNICODE` semantics, the Python 3 default for str patterns)
- Update the validation error message to remove the "ASCII" language
- Expose a new `is_valid_album_folder_name(name: str) -> bool` predicate from
  `models.py` as the single source of truth for album folder name validity
- Remove `ALBUM_PATTERN` from `scan.py` and replace both usages with
  `is_valid_album_folder_name`; also remove the now-unused `import re` from
  `scan.py`
- Add test cases covering diacritic titles in both model validation and
  scan discovery

## Capabilities

### New Capabilities

- `darkroom-album`: Rules governing what constitutes a valid album folder
  name, including the allowed character set for the title segment and the
  predicate function used by all modules to check validity.

### Modified Capabilities

## Impact

- `src/photo_darkroom_manager/models.py` — regex, error message, new public
  predicate function
- `src/photo_darkroom_manager/scan.py` — remove `ALBUM_PATTERN` and
  `import re`, import and use `is_valid_album_folder_name`
- `tests/test_models.py` — diacritic positive cases, updated rejection
  test, predicate tests
- `tests/test_scan.py` — diacritic folder appears in scanned tree
- `TODO.md` — mark line 10 done
