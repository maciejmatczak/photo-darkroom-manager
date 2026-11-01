# Agent Instructions

## Writing Markdown

Wrap all generated markdown files at 80 columns.

## Committing

Never commit automatically. When a coherent unit of work is done and verified,
propose a commit (scope and message) and wait for the user to approve it.

## Design approaches

### Core services

When a domain responsibility has several operations sharing state or rules,
consider grouping them into a service-like component that owns them, in the
spirit of a service layer between components; a plain function or attribute
is often enough. If a service fits, name it after the domain rather than the
pattern, keep it deep and unaware of its callers, and present it next to at
least one alternative so the choice is made, not assumed.

### Modules and their tests

A deep module that needs several files becomes a package (for example
`src/photo_darkroom_manager/core/library/`). Its tests mirror it: when the
module needs more than one test file, they go in a folder of the same name
(`tests/core/library/`, with `__init__.py`), one test file per submodule
(`test_layout.py`, `test_media.py`, `test_tree.py`, ...). Tests follow the
code they exercise, not the caller that uses it: a helper's tests live with
the module that owns the helper. Tests through the engine that span
several domains stay at the top of `tests/core/`.

### Core and frontends

The package has three subpackages: `core`, `cli` and `gui`. Frontends may
import the core; the core never imports a frontend or a UI library, and the
frontends never import each other. `lint-imports` enforces this in CI and
pre-commit; fix a broken contract by moving the code, not the contract.

## Branching (redesign line)

This checkout is on `dev-core-split`, a long-lived side line for the core
redesign: split logic into a GUI-independent core, make the GUI a thin layer
over it, and add a CLI on top of the same core. Expect breaking changes here.

- Treat `dev-core-split` as the base branch: open PRs for redesign work
  against `dev-core-split`, not `dev` or `main`.
- Bug fixes go to `dev` first (it must stay shippable), then get merged
  forward into `dev-core-split`. Never fix a bug only here.
- Sync by merging `dev` into `dev-core-split` (`git merge dev`). Never rebase
  this branch and never merge it back into `dev` until the redesign is done.
- When a fix on `dev` touches code being rewritten here, note it so it is
  ported, not lost in conflict resolution.
- The redesign ends with one PR `dev-core-split` -> `dev`; then the branch is
  deleted.
