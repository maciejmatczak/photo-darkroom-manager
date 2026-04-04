# Development

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs and manages Python)
- Python **3.13** (see `requires-python` in `pyproject.toml`; uv can install it for you)

## One-time setup

From the repository root:

1. **Install dependencies** (runtime + dev tools: Ruff, ty, pre-commit):

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

   That runs Ruff, **ty**, and the other hooks. You can also run tools directly:

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run ty check
   ```

## Day to day

- Commits run **Ruff** (check + format), **ty** (`ty check`), and file hygiene hooks; the **commit message** must follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat: …`, `fix: …`, `chore: …`).
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

## CI

On pushes and pull requests to `main` / `dev`, GitHub Actions runs separate jobs: **Ruff** (`ruff check`), **Ruff format** (`ruff format --check`), and **ty** (`ty check` after `uv sync --group dev`). That mirrors the main local checks even if someone skips hooks (`--no-verify`).

---

## Project notes

- tidy: organize all photos recurrently into parent folders based on relative image file
