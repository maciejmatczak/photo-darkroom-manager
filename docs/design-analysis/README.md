# Design analysis

A design exercise on the darkroom manager's core, following the process of
the field guide "Designing by Knowledge and Roles" (Ousterhout, with ideas
from DDD and hexagonal architecture where they help). The goal is a more
maintainable core, and learning, whichever way it turns out.

We go in small steps and record decisions here once they are settled. Code
and today's implementation are not inputs to the early phases: they describe
how the app is built, and these phases ask what it must do.

## Files

| File | Phase | Holds |
|---|---|---|
| [01-brief.md](01-brief.md) | 1 | What the app does, in the user's words |
| [02-context.md](02-context.md) | 2 | External systems, and the tags used in walkthroughs |
| [03-walkthroughs.md](03-walkthroughs.md) | 3 | One walkthrough per use case, with what each revealed |
| [knowledge.md](knowledge.md) | 4 | Living inventory of knowledge, updated in every phase |
| [05-ownership.md](05-ownership.md) | 5 | Who decides each piece, the grouping, change scenarios |
| [06-external.md](06-external.md) | 6 | Outside systems and where the boundaries go |
| [07-interfaces.md](07-interfaces.md) | 7 | What each piece offers its callers |

From Phase 5 on, the phases follow the design-by-knowledge-and-roles skill,
which merges the guide's "sort" and "group" phases into one: 5 ownership,
6 external systems, 7 interfaces, 8 structure, 9 complexity review.

## Status

| Phase | State |
|---|---|
| 1. Product brief | Done |
| 2. System context | Done |
| 3. Use-case walkthroughs | Done |
| 4. Knowledge inventory | Reviewed; keeps growing |
| 5. Ownership | Done |
| 6. External systems | Done; rclone adoption check open |
| 7. Interfaces | 7a-7j agreed (tidy; file transfer, watch, run log; publish, archive, rename and new batch checked against tidy; see as a query; cull, edit and open); set up and `SettingsStore` next |
| 8-9 | Not started |

## Working rules

- Use cases hold for any client (a stateless CLI or a long-running GUI).
  What follows from one client's lifetime is a design question for later.
- Decisions marked "easy to change" are change scenarios for Phase 5: the
  design is tested on how few modules each one touches.
- Use the domain's words. Design words (action, service, port) wait for the
  phases that decide them.

## Ideas parked for later phases

- **rclone for heavy file moves** (Phase 6): hand tidy, publish and archive
  moves to rclone as a subprocess, keeping them auditable without the app
  owning the movement. If adopted, rclone is a new external system: we hand
  it moves and read back a report. *Phase 6: moves get a port with an
  rclone adapter; adoption waits on whether rclone keeps the promises.*
- **Settings vs runtime values seeded from settings** (Phase 7): depends on
  the client's lifetime, for example the log level.
- **Folders by role** (Phase 8): lay out `core` by architecture role
  (`domain`, `application`, `ports`, `infrastructure`, adapters, a
  composition root) so one `lint-imports` layers contract enforces it.
  Every folder must hold something real.
- **A "Justified by" column** (Phases 6-8): each pattern names the cost it
  removes; anything kept only for practice is marked "exercise only".

## Lessons learned

- **Code in the context anchors the design.** In Phase 7 the "new" publish
  interface matched today's implementation, which had been read earlier in
  the same session. When independent alternatives matter, design in a
  fresh context that holds only these docs; otherwise, keep an option only
  if its reasons hold against a real alternative.
