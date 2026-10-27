## Context

Album folder names follow the pattern `YYYY-MM[-DD][ title]`. The title
segment is validated in `models.py` by
`_TITLE_ALLOWED = re.compile(r"^[a-zA-Z0-9_\- ]+$")`, which only allows
ASCII characters. Folders with diacritic titles (e.g., `2026-03 été`) pass
the scan-time prefix filter (`ALBUM_PATTERN` in `scan.py`) and appear in
the UI tree, but all actions (Publish, Archive, Rename) fail because
`AlbumFolderName` construction raises a `ValidationError`.

A second problem is that `scan.py` carries its own independent definition
of album folder validity (`ALBUM_PATTERN = re.compile(r"^\d{4}-\d{2}")`),
which only checks the date prefix and ignores the title entirely. This
creates two separate, diverging sources of truth for the same concept.

## Goals / Non-Goals

**Goals:**
- Allow Unicode letters (diacritics, non-Latin scripts) in album folder
  name titles
- Establish `models.py` as the single source of truth for album folder
  name validity
- Remove the `ALBUM_PATTERN` divergence from `scan.py`

**Non-Goals:**
- Supporting arbitrary Unicode (emoji, punctuation, control characters)
- Surfacing scan-time ignored paths (separate TODO item)
- Normalizing Unicode (NFKC/NFC) — deferred; OS handles this at the
  filesystem level
- Changing the date-portion validation

## Decisions

### 1. Use `\w` with Python 3 default Unicode semantics

**Decision:** Replace `r"^[a-zA-Z0-9_\- ]+$"` with `r"^[\w\- ]+$"`.

In Python 3, `\w` matches `[a-zA-Z0-9_]` plus all Unicode word characters
(letters, digits, combining marks) for `str` patterns by default —
`re.UNICODE` is implicit. This accepts `é`, `ą`, `ü`, `ñ`, Cyrillic, CJK,
etc., while continuing to reject characters that are illegal in Windows
filenames (`\ / : * ? " < > |`) and non-word punctuation.

**Alternatives considered:**
- *Explicit allowlist (`\p{L}\p{N}...`)* — requires the third-party
  `regex` library, unnecessary complexity.
- *Permissive blocklist (allow everything except Windows-illegal chars)* —
  too wide; would allow `?`, `*`, `!` which, while legal on POSIX, are
  unexpected in album names and could complicate path construction on mixed
  systems.
- *Keep ASCII, add explicit ranges (`a-zA-ZÀ-ÖØ-öø-ÿ...`)* — fragile,
  incomplete, hard to maintain.

### 2. Expose `is_valid_album_folder_name()` as the single predicate

**Decision:** Add a public `is_valid_album_folder_name(name: str) -> bool`
function to `models.py` that wraps `AlbumFolderName.from_str()` in a
try/except. All modules that need to test album folder name validity import
this function.

This makes `models.py` the authoritative layer and avoids duplicating the
validation logic in scan or elsewhere.

**Alternatives considered:**
- *Export the regex patterns* — callers would still need to duplicate the
  multi-step validation (parse pattern + title pattern). Fragile.
- *Move validation to a separate `validation.py`* — unnecessary indirection
  for a small, cohesive model.

### 3. Remove `ALBUM_PATTERN` from `scan.py`

**Decision:** Delete `ALBUM_PATTERN` and the `import re` that serves it.
Replace the two call sites in `_scan_year` and `rescan_subtree` with
`is_valid_album_folder_name(child_dir.name)`.

**Behavioral note:** This tightens scan slightly. Currently, a folder like
`2026-03 bad:name` (date prefix valid, title invalid) appears in the tree
but actions fail. After this change it is silently excluded from the tree.
This is the correct behaviour — a folder that cannot be acted on should not
appear as if it can. The broader concern about surfacing ignored paths is
tracked separately (TODO.md line 15).

## Risks / Trade-offs

- **Silent exclusion of edge-case folders** → Users with folders that have
  non-word, non-hyphen, non-space characters in titles will no longer see
  them in the tree. This is an improvement (no more ghost entries), but
  could surprise someone who had a workaround. Mitigation: error message
  update makes the constraint visible; the ignored-paths feature (TODO line
  15) will surface these explicitly in a future change.
- **Unicode title scope is wide** → `\w` accepts CJK, Arabic, etc. These
  are valid for users in those locales. The only downside is that some edge
  characters in obscure Unicode blocks may be unexpected. Acceptable
  trade-off given real-world album naming.

## Open Questions

- None — the approach is fully resolved by the exploration session.
