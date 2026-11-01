# engine/ specs

The contract between the core engine and any client: the GUI today, possibly
another front end or an index or database later. These specs cover
guarantees, stated as observable behavior of the engine's interface:

- Scanning: what a rescan refreshes and what it leaves untouched.
- Library index: how clients address, read and scan the library tree by
  node id, and when the scanned tree is dropped.
- Path resolution: one consistent darkroom, archive, and showroom location
  for every action and client.
- Requests: an action request is either executed or rejected with a reason,
  and only one action runs at a time.
- User config: loading, reading, updating and saving the user's
  configuration, and how its problems are reported.
- Engine status: the configured values the engine works with, whether it
  can work and why not, and its runtime log level.

**Belongs here** if a client could depend on it without knowing how the
engine is built.

**Does not belong here:**

- What the user sees or what lands on disk. That goes in `../app/`.
- Mechanics: thread pools, registries, event classes, versioning schemes,
  module layout. That goes in the change's `design.md`.

Quick check: if swapping the implementation (for example, a filesystem scan
replaced by a database index) would break a requirement, the requirement
describes mechanics, not a guarantee.
