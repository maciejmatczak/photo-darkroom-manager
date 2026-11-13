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

A command that moves, creates or renames files prints its plan, in that
action's own terms, and changes nothing:

```text
$ darkroom archive .
Archive 2 files, 1 already in the archive
From: ...\darkroom\Camera\2026\2026-10 Walk
To:   ...\archive\2026\2026-10 Walk\Camera

Moves: 2
  move a.jpg → a.jpg
  move b.jpg → b.jpg
Already in the archive: 1
  c.jpg → c.jpg (target already exists)

Decide before running:
  existing: 1 file(s) already in the archive stay in the darkroom (skip)

plan a22139c60dcc
run it: darkroom archive "id:Camera/2026/2026-10 Walk" --confirm a22139c60dcc
```

- `--confirm FINGERPRINT` runs the action only if its plan is still the
  one shown; if a file was added or removed since, it is refused and both
  fingerprints are printed. The fingerprint is derived from the plan and
  stored nowhere.
- `--apply` runs the action as it is prepared now.
- A plan with nothing to do (e.g. nothing to tidy) prints no `run it`
  line, is never run, and exits 0.
- The two options cannot be combined. `open`, `cull` and `edit` change no
  files and run at once.
- No command ever asks a question, so it is safe to run without a
  terminal.

### Conflicts

A conflict is a file whose target already holds a file, or two files that
need the same target. The preview lists them next to the free moves and
asks what to do with them (`Decide before running`). Without an answer,
running is refused (exit 3) before anything starts, and nothing moves.
`--on-conflict` answers:

- `skip` (tidy, archive, publish) moves the free files and leaves each
  conflicting file where it is; the result lists them as skipped.
- `replace` (publish only) puts the new file in place of the one already
  in the showroom. Republishing over existing files needs it.

Any other combination is a usage error (exit 2). The printed `--confirm`
command carries the option you gave. A file that appears at a target
while the action runs is skipped, or replaced when you chose `replace`.
Nothing is ever overwritten without `replace`.

### Jobs, progress and Ctrl+C

Tidy, archive, publish, rename and new batch, and every scan, run as one
job in the engine; open, cull and edit run at once, also while a job
runs.
While it runs, the command shows its progress on stderr when stderr is a
terminal (a counter and the current file, or a spinner for a scan) and
nothing extra otherwise; stdout carries only the result.

`rename` and `new-batch` are one step: they report no progress and
ignore Ctrl+C, but write a job log like the others. While any job runs,
another is refused as busy (exit 3), naming the job that runs.

A refusal (a stale plan, a missing answer, a taken name) happens before
any job starts. A job ends `done` whenever its action ran to the end,
also when a file failed or was skipped; the result says what happened
to each file. It ends `failed` only on an unexpected error.

Ctrl+C cancels the job: it stops between files, never in the middle of
one, prints its result (what was moved and what was left) and exits 130.

A move to another drive copies to a hidden `.NAME.darkroom-partial` file,
checks its size, puts it in place and only then removes the source; a
failed copy leaves the source and removes the partial file.

Each job writes an audit log to the `jobs` folder in the logs folder,
named `{date}_{time}_{name}_{description}.log` (for example
`2026-11-07_143012_archive_Camera-2026-2026-10-Walk.log`): the request
(action, node, fingerprint and answers), every step done, skipped or
failed, and the outcome. Job logs are kept when old application logs are
cleaned up.

### JSON and exit codes

With `--json` (before the command), stdout holds exactly one document:
`{"format": 1, "command": ..., "ok": ..., "result": ..., "error": ...}`.
A result is a node view, a plan or an action's result:

- A plan is `{kind: "plan", action, node_id, ...its own fields,
  questions, nothing_to_do, fingerprint, confirm}`; `confirm` is the
  command as argv, `null` when there is nothing to do. Its own fields
  differ per action, e.g. archive has `source`, `target`, `moves` and
  `conflicts`, rename has `folder` and `new_folder`.
- A result is `{kind: "result", action, outcome, message, ...its own
  fields, node_id, library_refreshed}`. Actions that move files report
  `moves` with `moved`, `replaced`, `failed`, `skipped` and `left` (the
  files a cancel left undone); archive adds `remaining`, the files still
  in the archived folder. `node_id` is the node afterwards, `null` when
  it is gone.

A refused run returns the current plan with an error. An error has a
`kind`, a `message` and, where known, a `fix`.
Logs go to stderr only: warnings by default, more with `-v` or `-vv`.

| Exit code | Meaning |
| --- | --- |
| 0 | Done, nothing to do, or a preview printed |
| 1 | The action failed while running |
| 2 | Usage error (bad options or arguments) |
| 3 | Refused; the error's `kind` says why (e.g. `not_allowed`, `busy`) |
| 4 | The engine is not ready (configuration missing or invalid) |
| 5 | No such node, or a path outside the darkroom |
| 130 | Cancelled with Ctrl+C |

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
