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
| [knowledge.md](knowledge.md) | 4 | Running inventory of knowledge, filled as we go |

## Status

| Phase | State |
|---|---|
| 1. Product brief | Done |
| 2. System context | Done |
| 3. Use-case walkthroughs | Done |
| 4. Knowledge inventory | Collected while walking through; to review |
| 5-9 | Not started |

## Working rules

- Use cases hold for any client (a stateless CLI or a long-running GUI).
  What follows from one client's lifetime is a design question for later.
- Decisions marked "easy to change" are change scenarios for Phase 6: the
  design is tested on how few modules each one touches.
- Use the domain's words. Design words (action, service, port) wait for the
  phases that decide them.
