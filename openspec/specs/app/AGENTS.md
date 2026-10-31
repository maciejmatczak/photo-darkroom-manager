# app/ specs

Behavior a user can see or rely on: what the screens show, which actions each
row offers, what an action does to files on disk, the library layout and
naming rules.

**Belongs here** if it would still hold after the internals were completely
rewritten. Write it as an observable result:

- "After a batch is created, its rows appear without a manual refresh."
- "Archive is offered only when the archive root is available."

**Does not belong here:**

- A guarantee the core gives its clients, such as request/rejection
  semantics, scan scope, or path resolution. That goes in `../engine/`.
- How something is done: class or module names, threads, registries, which
  node gets rescanned, framework choices. That goes in the change's
  `design.md`.

Quick check: if a requirement names a part of the code ("the core",
"the manager", "the UI SHALL rescan..."), restate it as what the user sees,
or move it.
