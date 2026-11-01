# Development

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs and manages Python)
- Python **3.13** (see `requires-python` in `pyproject.toml`; uv can install it for you)

## One-time setup

From the repository root:

1. **Install dependencies** (runtime + dev tools: Ruff, ty, import-linter, pre-commit):

   ```bash
   uv sync --group dev
   ```

2. **Install Git hooks** (lint/format on commit, conventional commit message on `commit-msg`):

   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type commit-msg
   ```

3. **Optional — validate the whole tree** before your first push (close to what CI runs):

   ```bash
   uv run pre-commit run --all-files
   ```

   That runs Ruff, **ty**, the import contracts, and the other hooks. You can also run tools directly:

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run ty check
   uv run lint-imports
   ```

## Day to day

- Commits run **Ruff** (check + format), **ty** (`ty check`), the import contracts (`lint-imports`), and file hygiene hooks; the **commit message** must follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat: …`, `fix: …`, `chore: …`).
- Run `uv run pre-commit run --all-files` anytime you want local hooks on the full tree without committing.
- Run `uv run ruff check .`, `uv run ruff format .`, or `uv run ty check` if you prefer calling tools directly (see `.cursor/rules/development-guide.mdc` for a suggested order).

**Merge/squash commits:** Messages produced by GitHub when merging may not be conventional; align with your team (e.g. squash with a conventional subject, or use merge strategies that satisfy the hook).

## Running the GUI (dev mode)

Start the GUI in your browser with hot reload enabled:

```bash
uv run python -m photo_darkroom_manager.gui.gui_app
```

This opens the app at `http://localhost:8090` in your default browser. Any file change triggers an automatic reload — no restart needed.

> The production entry point (`photo-darkroom-manager` / `dr-mng`) launches a native window instead. Use the command above during development only.

## Package layout and import contracts

`photo_darkroom_manager` has three subpackages: `core` (settings, the library
index, actions and the engine), `cli` and `gui`. Frontends import the core;
the core imports no frontend and no UI library (`nicegui`, `webview`), and
`cli` and `gui` do not import each other. `uv run lint-imports` checks this
from the `[tool.importlinter]` contracts in `pyproject.toml`.

## CI

On pushes to `main` / `dev` / `dev-core-split` and on all pull requests, GitHub Actions runs separate jobs: **Ruff** (`ruff check`), **Ruff format** (`ruff format --check`), **ty** (`ty check` after `uv sync --group dev`), and **Import contracts** (`lint-imports`). That mirrors the main local checks even if someone skips hooks (`--no-verify`).

---

## Project notes

- tidy: organize all photos recurrently into parent folders based on relative image file

## Branches

- `main`: releases.
- `dev`: day-to-day fixes and small features; must stay shippable.
- `dev-core-split`: long-lived redesign line (core / GUI / CLI split). PRs
  for redesign work target it; `dev` is merged into it regularly. Enable
  `git config rerere.enabled true` to reuse conflict resolutions.
