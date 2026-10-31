# Design

## Context

See proposal.md - Why. Main specs are flat (`core`, `user-interface`,
`action-*`, ...). The next changes (engine boundary, per-field settings) add
requirements on both sides of the UI/core line and need a stable place for
each.

## Goals / Non-Goals

**Goals:**
- A classification rule anyone can apply to a new requirement.
- Relocate every existing requirement without changing its meaning.

**Non-Goals:**
- Writing new engine requirements (engine API, events, settings); that is the
  engine-boundary change.
- Tightening or splitting existing requirements beyond the two restatements
  in `app/user-interface`.

## Decisions

### Classification rule

A requirement belongs in `app/` if it would still hold after the internals
were completely rewritten: what a user sees, can do, or finds on disk.

It belongs in `engine/` if it is a guarantee the core gives any client (the
GUI today, maybe another front end or an index later), stated as observable
behavior of the core's interface.

Mechanics (class names, threads, registries, refresh strategies) belong in
neither; they go in a change's design.md.

Applied here:
- "Refresh after creation" prescribed which node to rescan, which is a
  mechanism, so it is restated as the visible result.
- "Batch and subfolder rows" named "core destination resolution", so it is
  restated as "the same destination the action uses".
- "Destination resolution" still says actions and the user interface use the
  same resolution. It moves verbatim, and the engine-boundary change will
  rephrase it as an engine guarantee.

### Nested capability paths over name prefixes

`app/<capability>` and `engine/<capability>` use OpenSpec's nested spec ids
(1.15+), so the split is visible as folders.

- Alternative: flat `app-x` / `engine-x` prefixes, which work on any version.
  Rejected because the project already runs 1.15 and folders make the
  boundary harder to blur.

### Relocation through deltas

Each move is an ADDED delta at the new path, carrying the requirement text
verbatim, plus a REMOVED delta at the old path. This keeps the move inside the
normal archive flow, so `openspec validate` checks both sides.

- Alternative: moving folders by hand. Rejected because it bypasses
  validation and leaves no record in the change.

## Risks / Trade-offs

- [Archive may leave old spec files with no requirements] → A task checks
  after archive and deletes emptied `openspec/specs/<old-id>/` folders.
- [`album-title-diacritics` targets a pre-reorganization id] → That change
  is rebased onto `app/library-layout` after this one archives.
- [Older OpenSpec versions do not read nested ids] → The proposal states the
  1.15+ requirement.
