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
