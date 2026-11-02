# Development

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs and manages Python)
- Python **3.13** (see `requires-python` in `pyproject.toml`; uv can
  install it for you)

## One-time setup

From the repository root:

1. **Install dependencies** (runtime + dev tools: Ruff, ty, import-linter,
   pre-commit):

   ```bash
   uv sync --group dev
   ```

2. **Install Git hooks** (lint/format on commit, conventional commit
   message on `commit-msg`):

   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type commit-msg
   ```

3. **Optional — validate the whole tree** before your first push (close
   to what CI runs):

   ```bash
   uv run pre-commit run --all-files
   ```

   That runs Ruff, **ty**, the import contracts, and the other hooks. You
   can also run tools directly:

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run ty check
   uv run lint-imports
   ```

## Day to day

- Commits run **Ruff** (check + format), **ty** (`ty check`), the import
  contracts (`lint-imports`), and file hygiene hooks; the **commit
  message** must follow
  [Conventional Commits](https://www.conventionalcommits.org/) (e.g.
  `feat: …`, `fix: …`, `chore: …`).
- Run `uv run pre-commit run --all-files` anytime you want local hooks on
  the full tree without committing.
- Run `uv run ruff check .`, `uv run ruff format .`, or `uv run ty check`
  if you prefer calling tools directly (see
  `.cursor/rules/development-guide.mdc` for a suggested order).

**Merge/squash commits:** Messages produced by GitHub when merging may not
be conventional; align with your team (e.g. squash with a conventional
subject, or use merge strategies that satisfy the hook).

## Running the GUI (dev mode)

Start the GUI in your browser with hot reload enabled:

```bash
uv run python -m photo_darkroom_manager.gui.gui_app
```

This opens the app at `http://localhost:8090` in your default browser.
Any file change triggers an automatic reload — no restart needed.

> The production entry point (`photo-darkroom-manager` / `dr-mng`)
> launches a native window instead. Use the command above during
> development only.

## Running the CLI (experimental)

`darkroom` (short name `dr`) drives the core from a shell or an agent. It
is installed with the project by `uv sync`; run it as `uv run darkroom`
from the repository, or as `.venv/Scripts/darkroom` (Windows) or
`.venv/bin/darkroom` from anywhere, for example inside the darkroom.

```bash
uv run darkroom --help
uv run darkroom status
uv run darkroom config set darkroom D:/Photos/darkroom
uv run darkroom config set showroom D:/Photos/showroom
uv run darkroom config set archive D:/Photos/archive
```

`--config PATH` picks another configuration file; otherwise
`$PHOTO_DARKROOM_MANAGER_CONFIG_PATH` or the user configuration folder is
used. `config list` shows every key, `config get KEY` one value, and
`config set KEY VALUE` validates, stores and saves in one step.

### Commands

| Command | What it does |
| --- | --- |
| `status` | Whether the engine is ready, and what to fix |
| `config list \| get \| set` | Show or change settings |
| `inspect [TARGET] [--depth N]` | A node: files, issues, actions, children |
| `open`, `cull`, `edit TARGET` | Open the folder, or the configured app |
| `tidy`, `publish`, `archive TARGET` | Move files; preview first |
| `rename TARGET [--date D] [--title T \| --no-title]` | Rename a batch |
| `new-batch DEVICE --date D [--title T]` | Create a batch for a device |

Dates are `YYYY-MM` or `YYYY-MM-DD`. `rename` keeps the current date or
title when one is not given.

### Targets

A TARGET is a node id or a folder in the darkroom:

- `id:Camera/2026/2026-10 Walk` is an id; `id:` alone is the root.
- An absolute path, or one starting with `.`, is a path from the current
  folder: `darkroom archive .` inside a batch archives that batch.
- A bare name is tried as both. `2026-10 Walk` inside `Camera/2026` and
  `Camera/2026` from anywhere both work. If it names two different nodes,
  the command is refused; write `id:` or `./` to choose.
- Letter case may differ from the folders on disk; output always shows
  the on-disk names. Paths outside the darkroom are refused.

`inspect` without a target shows the current folder when it is in the
darkroom, and the root otherwise. It reads only that node's folders and
its ancestors', so it is fast in a large library.

### Preview, apply, confirm

A command that moves, creates or renames files prints its plan and
changes nothing:

```text
$ darkroom archive .
Archive 4 files
...
plan 8e9e0dd80ad2
run it: darkroom archive "id:Camera/2026/2026-10 Walk" --confirm 8e9e0dd80ad2
```

- `--confirm FINGERPRINT` runs the action only if its plan is still the
  one shown; if a file was added or removed since, it is refused and both
  fingerprints are printed. The fingerprint is derived from the plan and
  stored nowhere.
- `--apply` runs the action as it is prepared now.
- The two options cannot be combined. `open`, `cull` and `edit` change no
  files and run at once.
- No command ever asks a question, so it is safe to run without a
  terminal.

### JSON and exit codes

With `--json` (before the command), stdout holds exactly one document:
`{"format": 1, "command": ..., "ok": ..., "result": ..., "error": ...}`.
A result is a node view, a plan (with all its steps and the `confirm`
command as argv), or an execution result (steps done and failed, files
left, the node id afterwards). An error has a `kind`, a `message` and,
where known, a `fix`. Logs go to stderr only: warnings by default, more
with `-v` or `-vv`.

| Exit code | Meaning |
| --- | --- |
| 0 | Done, nothing to do, or a preview printed |
| 1 | The action failed while running |
| 2 | Usage error (bad options or arguments) |
| 3 | Refused; the error's `kind` says why (e.g. `not_allowed`) |
| 4 | The engine is not ready (configuration missing or invalid) |
| 5 | No such node, or a path outside the darkroom |

## Package layout and import contracts

`photo_darkroom_manager` has three subpackages: `core` (settings, the library
index, actions and the engine), `cli` and `gui`. Frontends import the core;
the core imports no frontend and no UI library (`nicegui`, `webview`), and
`cli` and `gui` do not import each other. `uv run lint-imports` checks this
from the `[tool.importlinter]` contracts in `pyproject.toml`.

## CI

On pushes to `main` / `dev` / `dev-core-split` and on all pull requests,
GitHub Actions runs separate jobs: **Ruff** (`ruff check`), **Ruff format**
(`ruff format --check`), **ty** (`ty check` after `uv sync --group dev`),
and **Import contracts** (`lint-imports`). That mirrors the main local
checks even if someone skips hooks (`--no-verify`).

---

## Project notes

- tidy: organize all photos recurrently into parent folders based on
  relative image file

## Branches

- `main`: releases.
- `dev`: day-to-day fixes and small features; must stay shippable.
- `dev-core-split`: long-lived redesign line (core / GUI / CLI split). PRs
  for redesign work target it; `dev` is merged into it regularly. Enable
  `git config rerere.enabled true` to reuse conflict resolutions.
