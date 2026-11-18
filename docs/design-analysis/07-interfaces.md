# Phase 7: Interfaces

What each piece offers its callers, designed from the caller's side and
judged by how much each interface hides. Code here is a sketch; names are
working labels.

## 7a. Application services: prepare, then run

A use case that changes files offers two calls, with the user's decision
between them. Publish is the example; tidy, archive, rename and new batch
follow the same shape. Application services are named after the activity
(`Publishing`, `Tidying`, `Archiving`).

```python
preview = core.publishing.prepare(path)
# the client shows the preview and gets the user's choice
report = core.publishing.run(preview, choice, watch=progress)
```

Shapes considered:

| Shape | Caller side | Verdict |
|---|---|---|
| **Prepare, then run** | `prepare(b)`, then `run(preview, choice, watch)` | Chosen |
| One call that asks | `publish(b, ask=..., watch=...)`; the client injects an approver | A callback cannot cross two CLI processes |
| Ask, then command | A read-only query, then `publish(b, on_clash, expecting=fingerprint)` | The client, not the use case, would own the preview; a big archive is walked twice |
| A run you steer | `run = start(b)`; `run.choose(...)`; the client watches its state | GUI-first; revisit if the GUI needs it |

Decided:

- **The use case owns the preview** (Phase 3): `run` needs a preview, so
  the preview exists by construction. Dropping a preview means calling `run`
  straight after `prepare` inside the use case (scenario 8).
- **The preview is plain data with a fingerprint** *(corrected in 7c)*.
  What crosses to the client and back is the preview; the plan stays in
  the core. `run` plans again, compares the fingerprint, and carries out
  the plan only if nothing changed.
- **Each use case has its own preview and report types**, in its own words
  (see 7c for tidy). The plan, the work file by file, stays hidden inside
  the core.
- **The client passes a watch** to `run`, for progress and stopping between
  files. Its shape is decided with the ports.

This matches today's code. The reasons above, not familiarity, are why it
was kept; see the lesson in the [README](README.md).

## 7b. Domain services: from a path to a batch, and back

What publish asks of the domain:

```python
class Darkroom:
    def batch_at(self, path: Path) -> Batch: ...         # or refuses
    def publish_folder(self, batch: Batch) -> Path: ...  # see 7e

class Showroom:
    def path_for(self, batch: Batch) -> Path: ...
```

Decided:

- **A caller names a folder by its path inside the darkroom.** A person
  types it in the CLI, a GUI uses it as the id of a node, and it means the
  same in a second process.
- **Two directions, one pair of names** *(renamed in 7f)*: `x_at(path)`
  recognises what is at a path (`batch_at`); `path_for(x)` says where it
  goes in an area (`Showroom.path_for`). First named with "place"
  (`batch_from_place`, `place_for_batch`) to survive a move to albums; but
  albums would change the return type too, so the abstract word protected
  nothing and made every call read oddly.
- *(Corrected in 7e)* The darkroom answers only where a batch's `PUBLISH`
  folder is (`publish_folder`). What in it is publishable belongs to the
  publish use case (Phase 5), so `publishable(batch)` was dropped.

## 7c. Tidy: the preview and the plan

Publish is parked; tidy is the hardest use case, so it is designed first
and the others are checked against it afterwards.

Method: what the user needs to see first, then what the plan must hold,
then its structure.

**What the user needs to see.** The normal case as a summary, the
exceptions explicitly:

| Need | Normal or exception | Detail |
|---|---|---|
| Photos and videos to tidy | Normal | Counts |
| Clashes: we know where it goes, but the place is taken or wanted twice | Exception | Each file, with its reason |
| Left alone: the recipe does not know where it goes | Exception | Each file, with its reason |

The choice (stop or skip) is not in the preview: it is the user's answer,
given to `run`, and its set is fixed for tidy.

**The preview and the plan.** Two objects, two jobs:

- **The plan** (`TidyPlan`) is the work, file by file. The recipe builds
  it, `run` carries it out, and it never leaves the core.
- **The preview** (`TidyPreview`) is what the user agrees to: the counts,
  the clashes, the files left alone, and the fingerprint of the plan.

```python
@dataclass(frozen=True)
class TidyPlan:                  # the work; never leaves the core
    folder: Path
    photos: list[Move]
    videos: list[Move]
    clashes: list[TidyClash]
    left_alone: list[LeftAlone]


@dataclass(frozen=True)
class TidyPreview:               # what the user agrees to
    folder: Path
    photos: int
    videos: int
    clashes: list[TidyClash]
    left_alone: list[LeftAlone]
    fingerprint: str             # of the plan


class Tidying:
    def prepare(self, path: Path) -> TidyPreview:
        return TidyPreview.of(self.recipe.plan(path))

    def run(self, preview, choice: StopOrSkip, watch) -> TidyReport:
        plan = self.recipe.plan(preview.folder)  # planning again: the check
        if fingerprint(plan) != preview.fingerprint:
            raise PlanChanged(preview)
        ...                                      # carried out: see 7d
```

Decided:

- **Fixed groups are separate fields**, in business order, not one list
  tagged by kind: the client handles each group differently.
- **The fingerprint comes from the plan**, hashing every move, clash and
  file left alone. Counts cannot prove the files are the same. Planning
  again at `run` is the check, not waste: nothing proves the disk is
  unchanged without looking again.
- **The per-file re-check stays inside the mover**, for the moments during
  the run, after the fingerprint has passed.
- **`Move` (a source and a target) is the mover's whole input**, shared by
  every use case *(7d adds a replace flag, for publish only)*.
- **Tidy never replaces**: its `run` takes `StopOrSkip`.
- Clashes are kept in full; the client decides how many to show.
- **A tidy clash is a `TidyClash`**, never a move: tidy cannot hand a
  clash to the mover *(named in 7e; both sides of the clash added in 7f)*.
- "Where they land" was dropped: the recipe fixes it, so it says nothing
  new.

**The report.** Sorted by what is new since the user agreed: failures are
the only news, so they are the one group shown file by file.

| Outcome | Known at the preview? | Detail |
|---|---|---|
| Moved | Yes, normal | Counts: photos, videos |
| Failed | No | Each file, with its reason |
| Skipped (clashes, when skip was chosen) | Yes | A count; named in the preview |
| Not reached | Yes, normal | A count, and why the run stopped |
| Left alone | Yes | The same list as the preview |

```python
@dataclass(frozen=True)
class TidyReport:
    folder: Path
    photos_moved: int
    videos_moved: int
    failed: list[Failure]        # file and reason
    skipped: int
    not_reached: int
    stopped: str | None          # "you stopped it", "clashes, as chosen"
    left_alone: list[LeftAlone]
    log: Path | None             # this run's record (7d)
```

- **`stopped` says why files were not reached**: the user stopped the run,
  or "stop if anything clashes" was chosen and nothing ran.
- The counts add up to the preview's total, so a test can assert it and a
  GUI can show a bar that sums to what was agreed.

## 7d. The mover, the watch and the run log

What the mover is given and hands back, how the client follows and stops a
run, and how each run gets its own record. Tidy is the example.

```python
@dataclass(frozen=True)
class Move:
    source: Path
    target: Path
    replace: bool = False                # set by publish only


@dataclass(frozen=True)
class MoveResult:                        # stays in the core
    moved: list[Move]
    replaced: list[Move]
    failed: list[Failure]                # incl. "taken since the preview"
    not_reached: list[Move]
    cancelled: bool                      # the watch said stop


class Mover(Protocol):                   # port (MoveFiles in Phase 6)
    def move(self, moves: list[Move], watch: RunWatch,
             run_log: RunLogger) -> MoveResult: ...


class RunWatch(Protocol):                # given by the client
    def progress(self, done: int, total: int) -> None: ...
    def cancelled(self) -> bool: ...


class RunLog(Protocol):                  # port: one log per run
    def start(self, action: str,
              path: Path) -> ContextManager[RunLogger]: ...
```

The use case:

```python
log = structlog.get_logger(__name__)     # app log: global, classic


class Tidying:                           # application service
    def run(self, preview, choice: StopOrSkip, watch) -> TidyReport:
        plan = self.recipe.plan(preview.folder)
        if fingerprint(plan) != preview.fingerprint:
            raise PlanChanged(preview)
        if plan.clashes and choice is StopOrSkip.STOP:
            return TidyReport.stopped_on_clashes(plan)
        with self.run_log.start("tidy", plan.folder) as run_log:
            run_log.info("tidy started", photos=preview.photos,
                         videos=preview.videos, choice=choice.name)
            result = self.mover.move(plan.photos + plan.videos,
                                     watch, run_log)
            run_log.info("tidy finished", moved=len(result.moved),
                         failed=len(result.failed))
        return TidyReport.of(plan, result, log=run_log.path)
```

The file adapter of the run log:

```python
class FileRunLog:                        # adapter
    @contextmanager
    def start(self, action, path):
        path = self.folder / f"{stamp()}-{action}.log"
        handler = logging.FileHandler(path)       # flushes every line
        base = logging.Logger(f"run.{action}")    # not getLogger: isolated
        base.addHandler(handler)
        try:
            yield RunLogger(structlog.wrap_logger(base), path)
        finally:
            handler.close()
```

Decided:

- **The clash choice stays in the use case.** On stop, the mover is not
  called; on skip, only the moves without a clash reach it. The mover knows
  no choices: replacing is a flag on each `Move`, set only by publish.
- **The mover answers with a `MoveResult`**, which stays in the core; each
  use case turns it into its own report. A file taken since the preview is
  a failure, found by the mover's per-file re-check.
- **The watch** reports progress and is asked `cancelled()` between files.
  "Cancelled" is the usual word for a cooperative stop (asyncio, .NET).
- **Two logs, two loggers:**

  | | Run log (audit) | App log (diagnostics) |
  |---|---|---|
  | Reader | The user, about one run | The developer, debugging |
  | Lifetime | One run | The whole process |
  | Created by | The `RunLog` adapter, per run | The composition root, at startup |
  | Reached through | An instance passed as an argument | `get_logger(__name__)` in each module |
  | Config | Fixed: a new file, every line flushed | Level and output, from settings |

- **`RunLog.start()` hands out an isolated logger for one run.** It is
  built with `logging.Logger`, not `getLogger`: it is not cached for the
  life of the process, does not inherit the app's handlers, and changes no
  global config. Two runs at once each write to their own file.
- **The run logger is passed explicitly**, like the watch: a value that
  lives for one run travels as an argument. Each piece writes what it
  knows: the use case the start (what was agreed, the choice) and the end,
  the mover each file.
- **The report gains `log`**, where to find this run's record. A run
  stopped on clashes moves nothing and opens no log.
- Mover adapters: an internal one (copy, verify, rename) and an rclone one
  (Phase 6).

Rejected:

- **A strict run record** with typed methods (`moved`, `failed`,
  `finished`). Nothing reads the run log back (Phase 2), and a free-form
  line would be needed anyway, which turns it back into logging. It returns
  if "undo the last run" or "resume a stopped run" is added: then the log
  has a reader and becomes a journal, a domain record.
- **A handler added to the global logging config for the run.** Hidden
  global state, and two runs at once would write into each other's files.

## 7e. Publish, checked against tidy

Publish follows tidy's shape: `run` takes the same steps, and publish has
its own preview, plan, report and clash type.

**What the user needs to see:**

| Need | Kind | Detail |
|---|---|---|
| New files | Normal | A count |
| Where they land | Normal | The showroom path |
| Clashes: the name is taken in the showroom | Warning | A count; each file and what takes its name, for the client to show |
| Left alone: subfolders of `PUBLISH`, same-name pairs in it | Exception | Each, with its reason |

```python
@dataclass(frozen=True)
class TidyClash:                         # never moved
    file: Path                           # ours
    target: Path                         # where the recipe sends it
    taken_by: Path                       # a file already there, or another
    reason: str                          # file of this run: "taken",
                                         # "wanted twice"


@dataclass(frozen=True)
class PublishClash:                      # replaced only if the user chooses
    file: Path                           # ours, in PUBLISH
    taken_by: Path                       # in the showroom

    def replacing(self) -> Move:
        return Move(self.file, self.taken_by, replace=True)


@dataclass(frozen=True)
class PublishPlan:                       # the work; never leaves the core
    batch: Batch
    showroom_path: Path
    new: list[Move]
    clashes: list[PublishClash]
    left_alone: list[LeftAlone]


@dataclass(frozen=True)
class PublishPreview:                    # what the user agrees to
    batch: Path                          # its path in the darkroom
    showroom_path: Path
    new: int
    clashes: list[PublishClash]          # a warning; no moves inside
    left_alone: list[LeftAlone]
    fingerprint: str                     # of the plan


@dataclass(frozen=True)
class PublishReport:
    batch: Path
    showroom_path: Path
    published: int
    replaced: int
    failed: list[Failure]
    skipped: int
    not_reached: int
    stopped: str | None
    left_alone: list[LeftAlone]
    log: Path | None
```

```python
class Publishing:                        # application service
    def prepare(self, path: Path) -> PublishPreview:
        return PublishPreview.of(self._plan(path))

    def run(self, preview, choice: StopSkipOrReplace,
            watch) -> PublishReport:
        plan = self._plan(preview.batch)
        if fingerprint(plan) != preview.fingerprint:
            raise PlanChanged(preview)
        if plan.clashes and choice is StopSkipOrReplace.STOP:
            return PublishReport.stopped_on_clashes(plan)
        moves = plan.new
        if choice is StopSkipOrReplace.REPLACE:
            moves += [clash.replacing() for clash in plan.clashes]
        with self.run_log.start("publish", plan.showroom_path) as run_log:
            result = self.mover.move(moves, watch, run_log)
        return PublishReport.of(plan, result, log=run_log.path)

    def _plan(self, path: Path) -> PublishPlan:
        batch = self.darkroom.batch_at(path)
        source = self.darkroom.publish_folder(batch)
        showroom_path = self.showroom.path_for(batch)
        # the files directly in source; subfolders are left alone;
        # names compared with showroom_path by the shared same-name rule
        ...
```

Decided:

- **Clashes are a warning, not an exception.** Publishing an edit again
  makes them normal. They are still shown, because replacing deletes the
  showroom copy, and the same name may hold a different edit: only the user
  can tell.
- **One word, two kinds of clash: `TidyClash` and `PublishClash`**, named
  after their use case like their plans. Not shared: the fields look alike,
  but the rules differ (tidy never moves a clash; publish may replace it).
  Only `PublishClash` can make a `Move` (`replacing`), so tidy cannot hand
  a clash to the mover *(revised in 7f: clashes hold both sides, no
  `Move`)*. "Already published" was rejected: the same name does not mean
  the same edit.
- `PublishClash` is where anything that helps the user judge a clash would
  go, such as the showroom copy's date or size.
- **The showroom path is shown** (`showroom_path`). Tidy dropped "where
  they land", but publish crosses into an area the darkroom view does not
  show and Immich reads; with albums it becomes the thing to check.
  Rejected names: `in_showroom` (reads as a yes/no flag), `target` and
  `destination` (technical, and `Move.target` exists).
- **One count of new files**, no photo and video split: publish treats
  every file in `PUBLISH` the same.
- **Left alone: subfolders of `PUBLISH`**, one line each, and pairs of
  names in it that differ only in letter case. A subfolder has nowhere to
  go in the showroom, but ignoring it silently could drop photos unseen,
  and refusing the whole publish is too harsh for a rare slip. A same-name
  pair is a darkroom problem, not a clash, so replace never picks between
  two files of one run.
- **Nothing to publish is an empty preview**, not an error. A path that is
  not a batch is refused in `prepare`, by `batch_at`.
- **What is publishable belongs to the use case** (Phase 5); the darkroom
  only answers where `PUBLISH` is (7b, corrected).
- The report is tidy's, with `published` and `replaced` counts.

## 7f. Archive, checked against tidy and publish

Archive follows the same shape. It differs in what it takes (a batch or a
subfolder in it), in what blocks it, and in cleaning up after itself.

**What the user needs to see:**

| Need | Kind | Detail |
|---|---|---|
| Files to archive | Normal | A count |
| Where they land | Normal | The archive path |
| Clashes: the name is taken in the archive | Exception | Each file and what takes its name |
| Blockers: a file in the archive where a folder must go | Exception | Each blocker, with how many files it holds back |

**A batch or a subfolder in it.** The domain recognises a path as a
folder in a batch, and the archive says where that folder goes:

```
darkroom:  Phone/2024/2024-05-01 Trip/Selects/Day1      <- the user picks
archive:   2024/2024-05-01 Trip/Phone/Selects/Day1
                                     └─ the batch's path, then the same
                                        subfolder as in the darkroom
```

```python
@dataclass(frozen=True)
class BatchFolder:                       # value object
    batch: Batch
    subfolder: Path                      # "Selects/Day1"; empty for the batch


class Darkroom:                          # domain service
    def batch_at(self, path: Path) -> Batch: ...         # or refuses
    def folder_at(self, path: Path) -> BatchFolder: ...  # or refuses
    def publish_folder(self, batch: Batch) -> Path: ...


class Showroom:                          # domain service
    def path_for(self, batch: Batch) -> Path: ...


class Archive:                           # domain service
    def path_for(self, folder: BatchFolder) -> Path: ...
```

**Clashes hold both sides.** A clash is two items: our file and the one in
the way.

```python
@dataclass(frozen=True)
class ArchiveClash:                      # never moved
    file: Path                           # ours, in the darkroom
    taken_by: Path                       # in the archive


@dataclass(frozen=True)
class ArchiveBlocker:
    archive_file: Path                   # a file where a folder must go
    holds_back: int                      # darkroom files it keeps out


@dataclass(frozen=True)
class ArchivePlan:                       # the work; never leaves the core
    folder: BatchFolder
    path: Path                           # in the darkroom
    archive_path: Path
    moves: list[Move]                    # subfolders kept
    clashes: list[ArchiveClash]
    blockers: list[ArchiveBlocker]


@dataclass(frozen=True)
class ArchivePreview:                    # what the user agrees to
    path: Path                           # in the darkroom
    archive_path: Path
    files: int
    clashes: list[ArchiveClash]
    blockers: list[ArchiveBlocker]
    fingerprint: str                     # of the plan


@dataclass(frozen=True)
class ArchiveReport:
    path: Path
    archive_path: Path
    archived: int
    failed: list[Failure]
    skipped: int                         # clashes and blocked files
    not_reached: int
    stopped: str | None
    kept_folders: list[Path]             # emptied, but held open elsewhere
    log: Path | None
```

**Removing emptied folders goes to the mover**, as a second method:

```python
class Mover(Protocol):                   # port
    def move(self, moves, watch, run_log) -> MoveResult: ...
    def remove_empty_folders(self, under: Path,
                             run_log) -> list[Path]: ...  # the kept ones


class Archiving:                         # application service
    def prepare(self, path: Path) -> ArchivePreview:
        return ArchivePreview.of(self._plan(path))

    def run(self, preview, choice: StopOrSkip, watch) -> ArchiveReport:
        plan = self._plan(preview.path)
        if fingerprint(plan) != preview.fingerprint:
            raise PlanChanged(preview)
        if (plan.clashes or plan.blockers) and choice is StopOrSkip.STOP:
            return ArchiveReport.stopped_on_clashes(plan)
        with self.run_log.start("archive", plan.archive_path) as run_log:
            result = self.mover.move(plan.moves, watch, run_log)
            kept = self.mover.remove_empty_folders(plan.path, run_log)
        return ArchiveReport.of(plan, result, kept, log=run_log.path)

    def _plan(self, path: Path) -> ArchivePlan:
        folder = self.darkroom.folder_at(path)
        archive_path = self.archive.path_for(folder)
        # every file under path, its subfolders kept below archive_path;
        # names compared by the shared same-name rule; blockers found
        ...
```

Decided:

- **Clashes are an exception here**, not a warning as in publish. The
  archive holds source material and only grows: the same name there is two
  originals with one name, or a copy left by an earlier run. Each is shown;
  nothing is replaced.
- **Every clash holds both sides**: our `file` and what it is `taken_by`.
  `taken_by` is the file really there, not the target recomputed: names
  match ignoring letter case, so `IMG_1.jpg` can clash with `img_1.JPG`.
  Tidy keeps `target` too, because a "wanted twice" clash is between two
  of our own files. No clash holds a `Move`; only `PublishClash` can make
  one, and its replace writes over `taken_by` itself, so no pair of names
  differing in case is created. With no moves inside, every preview
  carries its clashes as they are (7c and 7e updated).
- **A blocker is shown once**, with how many files it holds back, not as
  every file below it: the user fixes the one file.
- **Nothing is left alone**: archive asks no questions about the folders.
- **Merging is not shown.** A clean merge looks like a fresh archive to the
  user; anything that can go wrong in one is a clash or a blocker. The
  archive path is shown, as in publish: it is another area.
- **`BatchFolder`** names "a folder in a batch": the batch, and its
  `subfolder` (empty for the batch itself). It replaces a tuple of a batch
  and a leftover path. "Everything below keeps its folders" stays inside
  `Archive.path_for`.
- **Paths, not places.** `x_at(path)` recognises what is at a path;
  `path_for(x)` says where it goes in an area. The area called says which
  area, the argument's type says what for. 7a-7e renamed to match.
- **`StopOrSkip` is shared with tidy**, unlike the clash types. It is named
  by its content (the set {stop, skip}), not by a role whose meaning
  depends on the use case. If tidy gains a choice, tidy takes a new type.
- **Removing emptied folders is the mover's**, a change to the disk under
  "plan and carry out". rclone does it as part of a move
  (`--delete-empty-src-dirs`). A second method leaves tidy and publish
  untouched. It takes one folder, not a planned list: which folders end up
  empty depends on what moved. Folders held open elsewhere are returned
  and reported; the cleanup may fail without anything being wrong.
- **The pre-check for unpublished files** (change scenario 3) becomes one
  more warning group on `ArchivePreview` later, touching only the archive
  use case.
