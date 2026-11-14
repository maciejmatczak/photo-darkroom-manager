# Phase 5: Ownership

Who owns each piece of knowledge from [knowledge.md](knowledge.md). This
phase covers the sort by who decides, the grouping by decision, and the
change scenarios that test the grouping.

## Sort by who decides

Test: who would you ask to settle it?

- **Domain:** the photographer; the app's own rules and choices.
- **Outside system:** an operating system, filesystem or tool; technical
  detail kept behind a boundary.
- **Infrastructure:** generic engineering with no photo rules in it.

| Who decides | Knowledge |
|---|---|
| Domain | Required vs optional settings; areas never overlap; a feature is disabled until configured; recognising folders (the layout); unrecognised folders shown, not walked into; which devices exist; the batch name format; a batch sits in the year of its date; a new batch gets `PUBLISH`; names are unique on every supported system; a batch's name is shared across areas; what each folder kind allows; how counts and marks add up; photo and video classification; the tidy recipe; where a batch lands in the showroom; what is publishable; where a folder lands in the archive; which use cases preview and wait; pre-checks; clash choices; the plan is honoured (drift between preview and run is caught); never half-written; every file is recorded; what a run reports; removing emptied folders; the first-image guess; which tokens a command template offers |
| Outside system | What makes a folder name safe on each system; when two names are the same on each system (case, and possibly Unicode forms); how to start a program and open the file manager on each OS; how a file is moved across drives (copy, verify, rename; or rclone); the template syntax (Jinja) |
| Infrastructure | A long run can be watched and stopped between files; where and how run records are written; what goes stale when the darkroom setting changes |

## Decisions

- **Uniqueness is one common rule across systems.** The app aims to be safe
  on Windows and Unix (macOS too if it costs little). The domain rule is
  "names are unique on every supported system"; each system's own idea of
  sameness (letter case, possibly Unicode forms) is outside-system
  knowledge the rule is built from.
- **The re-check is a domain rule, not plumbing.** The user agrees to a
  plan; anything off the plan by the time it runs (a target taken since the
  preview) must be caught. How each move checks is part of moving files.
- **Staleness after a darkroom change is infrastructure.** It is rare
  (usually a one-time setup) but must be supported.
- Halves with different owners were split: what a run records (domain) vs
  where it is written (infrastructure); which tokens exist (domain) vs the
  template syntax (outside system).

## Grouping by decision

Each group owns the decisions that change together. Names are working
labels, not module names.

| Group | Owns | Changes when |
|---|---|---|
| Settings | Required vs optional settings; areas never overlap | What the app needs to run changes |
| Darkroom layout | Recognising folders by position and name; unrecognised folders; which devices exist; a batch sits in the year of its date; a new batch gets `PUBLISH` | The darkroom's organisation changes |
| Showroom layout | Recognising the showroom's folders; where a batch lands there | Albums arrive; the showroom is read |
| Archive layout | Recognising the archive's folders; where a darkroom folder lands there, merging | The archive's organisation changes |
| Batch | Its identity (device, date, title) and its name: built from date and title, read back | The name format changes |
| Name rules | Names are unique on every supported system | Supported systems change |
| Media | Photo, video or other | New file types appear |
| Tidy recipe | What is untidy and where each file belongs | Tidying is tweaked (often) |
| What can be done where | What each folder kind allows; features disabled until configured | Features are added or removed |
| Safe transfer | The plan is honoured; never half-written; every file recorded; how clashes are handled; what a run reports | The safety promises change |
| Each use case | Its own steps and choices: preview or not, which clash choices it offers, pre-checks, what is publishable, cleanup after archive, the first-image guess | That use case changes |
| Command template | Which tokens exist; rendering for a folder | Templates gain tokens |

Decided:

- **Each area has its own layout group**, self-contained, owning how its
  folders are recognised and where a batch lands in it. The showroom and
  archive will be read later, the same way as the darkroom.
- **The batch is its own group** because it moves between the areas: each
  layout reads or places a batch, and the batch carries its identity and
  name between them.
- Safe transfer keeps the promises and each use case keeps its choices:
  "publish may replace" belongs to publish, "a replace never half-writes"
  to safe transfer.

## Change scenarios

Changes we expect, taken from the decisions marked "easy to change". Each
is counted against three splits: the grouping above, a noun-based split
(`Batch`, `Device`, `Folder`, `File`), and today's code. The code column
counts files only; it is a measure, not a source of design.

| # | Scenario |
|---|---|
| 1 | Albums: a batch publishes into an album instead of `YEAR/BATCH/DEVICE` |
| 2 | Tidy tweak: a video in a subfolder of `PHOTOS` moves to the matching place under `VIDEOS` |
| 3 | Archive pre-check: warn when `PUBLISH` still has unpublished files |
| 4 | Rename follows: renaming a batch also renames it in the showroom and archive |
| 5 | The batch name gains a time: `2026-10-05 1430 Walk` |
| 6 | Devices come from the config instead of the darkroom's top folders |
| 7 | Heavy moves go through rclone |
| 8 | Preview is added to or dropped from a use case |

Held in reserve: unrecognised folders show counts; an emptied year folder
is removed after rename.

### Counts

Groups or files touched. Lower is better; a touch that is local and
obvious in each place it lands is better than one that is hidden.

| # | Grouping | Noun split | Today's code |
|---|---|---|---|
| 1 | 1: showroom layout | 2: `Batch`, `Folder` | 2: `paths.py`, `publish.py`; the showroom and archive places are one function |
| 2 | 1: tidy recipe | 2: `File`, `Folder` | 2: `library/media.py` (what is untidy), `actions/tidy.py` (where it goes) |
| 3 | 1: archive use case | 2: `Folder`, archive | 2-3: `archive.py`, the CLI answers and render |
| 4 | 3: rename, showroom layout, archive layout | 1: `Batch`, which then knows every area | 3-4: `rename.py`, `paths.py`, engine roots, CLI render |
| 5 | 1: batch | 1: `Batch` | 3: `layout.py` (two patterns), `rename.py` (builds the name's parts), `new_batch.py` |
| 6 | 2: darkroom layout, settings | 2: `Device`, settings | 3: `engine.py`, `user_config.py`, CLI |
| 7 | 1: safe transfer | 1: `File` | 2: `file_utils.py`, `actions/_moves.py` |
| 8 | 1: that use case | 2+: no home; each use case and its caller | 4: the use case, the engine's prepare/run pair, the CLI command table, render |

What the counts show:

- The grouping scores 1 on six of eight scenarios. Scenario 4 touches three
  groups, but each touch is local: the use case asks each area's layout to
  rename one batch.
- The noun split scores well on 4 and 5 by putting more into `Batch`; it
  then knows every area's layout, which is the leak scenario 1 exposes.
- Today's code spreads two decisions: the tidy recipe lives in two
  packages, and preview is decided by the client's command table as well as
  by each use case.
