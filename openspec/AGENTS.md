# Specs: what and how

Specs live in two layers. Each requirement belongs to exactly one.

## app/: what the user gets

Expectations and experience only: what a user sees, decides and can rely
on, what lands on disk, the library layout and naming rules.

- **Belongs here** if it would still hold after the internals were
  completely rewritten. Write it as an observable result:
  - "After a batch is created, its rows appear without a manual refresh."
  - "A failed move leaves the photo where it was."
- **Does not belong here:** means. No copying, checking, hashing,
  threads, jobs, plans, engine calls, or names of parts of the code.
- **Test:** if a sentence explains how a result is reached, it is in the
  wrong place. Restate it as what the user sees, or move it to engine/.

## engine/: how the engine delivers it

The contract between the engine and any client (the GUI, the CLI, later
an index or a database): its calls, refusals, jobs and states, and how a
guarantee is kept, e.g. a verified copy before a source is removed.

- **Belongs here** if a client could depend on it without reading the
  code.
- **Does not belong here:** what the user sees (that goes in app/), or
  how the code is built: modules, classes, registries, data shapes.
- **Test:** if swapping the implementation (a filesystem scan replaced
  by a database index) would break a requirement, it describes code, not
  a guarantee.
