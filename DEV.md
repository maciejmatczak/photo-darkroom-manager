# Development

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs and manages Python)
- Python **3.14+** (see `requires-python` in `pyproject.toml`; uv can install it for you)

## One-time setup

From the repository root:

1. **Install dependencies** (runtime + dev tools: Ruff, pre-commit):

   ```bash
   uv sync --group dev
   ```

2. **Install Git hooks** (lint/format on commit, conventional commit message on `commit-msg`):

   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type commit-msg
   ```

3. **Optional — validate the whole tree** before your first push (matches what CI runs):

   ```bash
   uv run pre-commit run --all-files
   ```

## Day to day

- Commits run **Ruff** (check + format) and file hygiene hooks; the **commit message** must follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat: …`, `fix: …`, `chore: …`).
- Run `uv run pre-commit run --all-files` anytime you want the same checks as CI without committing.
- Run `uv run ruff check .` or `uv run ruff format .` if you prefer calling Ruff directly.

**Merge/squash commits:** Messages produced by GitHub when merging may not be conventional; align with your team (e.g. squash with a conventional subject, or use merge strategies that satisfy the hook).

## CI

GitHub Actions runs `uv sync --group dev` and `pre-commit run --all-files` on pushes and pull requests so skipped local hooks (`--no-verify`) do not bypass checks on the server.

---

## Project notes

- tidy: organize all photos recurrently into parent folders based on relative image file
