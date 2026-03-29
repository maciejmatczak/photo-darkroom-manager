---
name: new-album CLI command
overview: Add a `new-album` Typer command that prompts for year, month, and optional album name, then creates `<DARKROOM>/<YEAR>/<YYYY-MM[ name]>/` plus `PUBLISH/`, using existing album validation. Config loading stays as today (find darkroom.yaml from cwd); README gains a bottom “Project notes” TODO for cwd-independent config.
todos:
  - id: new-album-cmd
    content: "Implement new-album: prompts (year, month, optional name), validate DarkroomYearAlbum, mkdir album + PUBLISH; idempotent exists path (exit 0, print full path)"
    status: pending
  - id: docs-readme
    content: "README: document new-album; add Project notes section at bottom with TODO for config resolution (cwd-independent darkroom.yaml)"
    status: pending
isProject: false
---

# Add `new-album` command

## Collaboration (how we work)

When requirements, edge cases, or implementation choices **do not add up**, **pause and discuss** with you: state the tension, **propose 2–3 concrete options**, and **you choose**. This applies during implementation, not only planning.

## Domain rules (already in code)

- Darkroom layout: `[DARKROOM/<YEAR>/<ALBUM>/](BIG_PICTURE.md)` where `ALBUM` is the **folder name**.
- `[DarkroomYearAlbum](src/photo_darkroom_manager/darkroom.py)` requires:
  - `year`: 4-digit string.
  - `album` folder name: regex `^\d{4}-\d{2}.`* — i.e. `**YYYY-MM` prefix**, then optional suffix (typically space + name).

## Prompts (interactive)

Order:

1. **Year** — `typer.prompt` with default **current calendar year** (`str(datetime.now().year)`).
2. **Month** — `typer.prompt` with default **current calendar month** (1–12; accept user input flexibly, normalize to zero-padded `MM` in the folder name).
3. **Album name (optional)** — prompt with empty default; strip whitespace; if empty, folder name is `**YYYY-MM` only**; if non-empty, folder name is `**YYYY-MM <name>`** (single space after `MM` to match common style and the regex).

Reject or normalize unsafe folder characters (e.g. path separators, `..`) — if ambiguous, follow the collaboration rule above.

## Config loading — **no change in this task**

Keep `**[find_darkroom_yaml()](src/photo_darkroom_manager/config.py)`** as-is (walk parents from `Path.cwd()` for `darkroom.yaml`). The **album path** is still driven by `**settings.darkroom`** (not “create under cwd”), so the **operation** is not tied to cwd for *where* the folder goes; **discovering** `darkroom.yaml` still requires running from a directory under the tree that contains it (same as other commands today).

**Documentation:** Add a **“Project notes”** section at the **bottom** of `[README.md](README.md)` with a **TODO** bullet: resolve `**darkroom.yaml` without relying on cwd** (e.g. env var, global config path, or `--config`) — deferred from this feature.

## `new-album` behavior

1. `cli_load_settings()` — unchanged signature; no `--config` / env / ContextVar work in this task.
2. Prompts: year → month → optional album name (as above).
3. Build folder name: `f"{year}-{month:02d}"` + optional  `f"{name}"` after validation/sanitization.
4. Target album directory: `settings.darkroom / year / folder_name`.
5. **Validate** with `DarkroomYearAlbum(year=..., album=folder_name, album_path=..., relative_subpath=Path(year)/folder_name)`.
6. **If `album_path` already exists:** print an informational message that the album folder **already exists**, print the **full absolute path**, **exit with code 0** (no error; idempotent / safe re-run).
7. **If it does not exist:** `album_path.mkdir(parents=True)`, then create `**album_path / "PUBLISH"`** (`mkdir` — no need for `exist_ok` if we only create when album was missing; if we ever create PUBLISH in isolation, match expected semantics).
8. On **successful creation**, print the **full absolute path** of the **album directory** (and optionally mention `PUBLISH/` was created — your call during implementation; at minimum the album path as requested).

## Files to touch


| File                                                                     | Change                                                                                                                                                 |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `[src/photo_darkroom_manager/cli.py](src/photo_darkroom_manager/cli.py)` | New `@app.command("new-album")`: prompts, validation, mkdir album + `PUBLISH/`, exists branch (info + exit 0 + full path), success branch (full path). |
| `[README.md](README.md)`                                                 | Document `new-album` in Commands; add **Project notes** at bottom with TODO for cwd-independent config resolution.                                     |


## Out of scope

- `**PHOTOS/` / `VIDEOS/`** under the new album (still only what you need for “new album” scaffolding).
- **Automated tests** — repo has no test suite today; optional follow-up.

## Verification

After implementation: `uv run ruff check .` and `uv run ruff format .` per [development-guide](.cursor/rules/development-guide.mdc). Manually run `photo-darkroom-manager new-album` from a directory that can find `darkroom.yaml` and confirm folder + `PUBLISH/` layout.
