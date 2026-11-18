# Phase 6: External systems

Which outside systems the core talks to, and where the boundaries go. The
change scenarios in [05-ownership.md](05-ownership.md) are the judge.

**The rule: a resource the app uses gets a port; the medium the domain is
made of does not.** A port keeps the core free of how an outside resource
works (its location, format, OS details). The darkroom's folders are not
outside detail: the darkroom *is* a folder organisation. A settings file is.

## Outside systems

| System | Direction | What the core needs |
|---|---|---|
| The user, through any client | Drives us | Start a use case, answer its questions, watch and stop a run |
| The filesystem | Driven | Read folders and files; create, rename and remove folders; move files |
| External apps (cull, edit, file manager) | Driven | Start a program on a folder |
| Settings storage | Driven | Read and store the settings |
| Run log | Driven | Record each file a run touches; survive a crash |

The darkroom, showroom and archive are not outside systems. They are
domain areas, each a root path in the filesystem plus its own layout.

## Decided

| Decision | Justified by |
|---|---|
| **No port for the filesystem.** The areas are folder organisations; the filesystem is what the domain is made of, not something foreign to translate. Tests use real temporary folders | A port would be a shallow proxy with nothing to swap |
| **No port per area.** | A move between two areas would have no owner |
| **A port for moving files**, with an internal adapter and an rclone adapter chosen by a setting | Scenario 7 (rclone) |
| **A port for settings storage** (`SettingsStore`: load, save), with a file adapter. Set up is a use case: its application service checks the new settings and stores them through the port. The composition root reads them through the same port at startup | A resource with a location and a format; the core never depends on either |
| **A port for the run log** (`RunLog`), with a file adapter. *Phase 7d: its one call starts a run and hands out that run's own logger; the app's diagnostic log is separate* | A resource; where and how records are written stays outside the core (Phase 5 sort) |
| **A port for external apps** (`ExternalApps`), with an OS adapter | A resource; how to start a program or the file manager differs per OS, and tests never start real programs |
| **Plan and carry out.** Domain services only decide and answer in paths. Every change to the disk (create folders, rename, move files, remove emptied folders) is planned, then carried out by one infrastructure mechanism, which re-checks the plan before acting | Scenario 8 (add or drop a preview) and "the plan is honoured", across five use cases |

Under "plan and carry out", a domain service like the darkroom's never
touches the disk to change it; it says what should exist and where. With
"the darkroom does it" instead, adding a preview would make the domain
service grow planning, re-checking and doing, and rename would need its own
copy of the same.

Ports so far: `MoveFiles`, `SettingsStore`, `RunLog`, `ExternalApps`.
Names are working labels; their methods are decided in Phase 7 (`MoveFiles`
became `Mover` in 7d, then `FileTransfer` in 7g: it transfers files, and
a folder rename is not one of its jobs).

## Still open

- Whether rclone can keep the safety promises (the plan is honoured, never
  half-written). It decides whether the rclone adapter is adopted, not the
  port.
- After settings change in a long-running client, what is built from the
  old settings is stale and must be rebuilt (Phase 7, client lifetime).
  *Phase 7i: the core holds no view between calls, so only what is built
  from the settings remains to rebuild.*
