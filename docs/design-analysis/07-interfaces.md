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
- **The per-file re-check stays inside the file transfer**, for the moments
  during the run, after the fingerprint has passed.
- **`Move` (a source and a target) is the file transfer's whole input**,
  shared by every use case *(7d adds a replace flag, for publish only)*.
- **Tidy never replaces**: its `run` takes `StopOrSkip`.
- Clashes are kept in full; the client decides how many to show.
- **A tidy clash is a `TidyClash`**, never a move: tidy cannot hand a
  clash to the file transfer *(named in 7e; both sides added in 7f)*.
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

## 7d. The file transfer, the watch and the run log

What the file transfer is given and hands back, how the client follows and
stops a run, and how each run gets its own record. Tidy is the example.
The port was first called `Mover`; 7g renamed it `FileTransfer`.

```python
@dataclass(frozen=True)
class Move:
    source: Path
    target: Path
    replace: bool = False                # set by publish only


@dataclass(frozen=True)
class TransferResult:                    # stays in the core
    moved: list[Move]
    replaced: list[Move]
    failed: list[Failure]                # incl. "taken since the preview"
    not_reached: list[Move]
    cancelled: bool                      # the watch said stop


class FileTransfer(Protocol):            # port (MoveFiles in Phase 6)
    def run(self, moves: list[Move], watch: RunWatch,
            run_log: RunLogger) -> TransferResult: ...


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
            result = self.transfer.run(plan.photos + plan.videos,
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

- **The clash choice stays in the use case.** On stop, the file transfer is
  not called; on skip, only the moves without a clash reach it. The file
  transfer knows no choices: replacing is a flag on each `Move`, set only
  by publish.
- **The file transfer answers with a `TransferResult`**, which stays in the
  core; each use case turns it into its own report. A file taken since the
  preview is a failure, found by the transfer's per-file re-check.
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
  the file transfer each file.
- **The report gains `log`**, where to find this run's record. A run
  stopped on clashes moves nothing and opens no log.
- File transfer adapters: `InternalTransfer` (copy, verify, swap in) and
  `RcloneTransfer` (Phase 6).

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
            result = self.transfer.run(moves, watch, run_log)
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
  a clash to the transfer *(revised in 7f: clashes hold both sides, no
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

**Removing emptied folders goes to the file transfer**, as a second method:

```python
class FileTransfer(Protocol):            # port
    def run(self, moves, watch, run_log) -> TransferResult: ...
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
            result = self.transfer.run(plan.moves, watch, run_log)
            kept = self.transfer.remove_empty_folders(plan.path, run_log)
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
- **Removing emptied folders is the transfer's**, a change to the disk under
  "plan and carry out". rclone does it as part of a move
  (`--delete-empty-src-dirs`). A second method leaves tidy and publish
  untouched. It takes one folder, not a planned list: which folders end up
  empty depends on what moved. Folders held open elsewhere are returned
  and reported; the cleanup may fail without anything being wrong.
- **The pre-check for unpublished files** (change scenario 3) becomes one
  more warning group on `ArchivePreview` later, touching only the archive
  use case.

## 7g. Rename: a folder change, not a file transfer

Rename keeps the shape (`prepare`, a preview, `run`) and drops the parts
that solve problems it does not have.

**What the user needs to see:**

| Need | Kind | Detail |
|---|---|---|
| The batch now and after | Normal | Two paths, e.g. `Phone/2024/2024-05-01 Trip` to `Phone/2025/2025-01-03 Trip` |
| The name does not change | Normal | "Nothing to change" |

```python
@dataclass(frozen=True)
class NameChange:                        # value object: what the user asked
    date: BatchDate | None = None        # None: keep
    title: str | None = None             # None: keep
    drop_title: bool = False             # refused together with a title


@dataclass(frozen=True)
class RenamePreview:                     # the whole plan, small enough to show
    path: Path                           # the batch now
    new_path: Path
    change: NameChange

    @property
    def unchanged(self) -> bool:
        return self.new_path == self.path


class Darkroom:                          # domain service
    def batch_at(self, path: Path) -> Batch: ...         # or refuses
    def path_for(self, batch: Batch) -> Path: ...        # DEVICE/YEAR/BATCH


class Renaming:                          # application service
    def prepare(self, path: Path, change: NameChange) -> RenamePreview:
        return self._plan(path, change)

    def run(self, preview: RenamePreview) -> Path:
        if self._plan(preview.path, preview.change) != preview:
            raise PlanChanged(preview)
        folders.rename(preview.path, preview.new_path)  # infrastructure
        log.info("renamed", path=..., new_path=...)     # app log
        return preview.new_path

    def _plan(self, path: Path, change: NameChange) -> RenamePreview:
        batch = self.darkroom.batch_at(path)
        new_path = self.darkroom.path_for(batch.renamed(change))
        # another folder there with the same name, ignoring case: NameTaken;
        # changing only the case of this batch's own name is allowed
        return RenamePreview(path, new_path, change)
```

On the caller side:

```python
change = NameChange(title="Trip to Lisbon")             # date kept
preview = core.renaming.prepare(path, change)
if not preview.unchanged and confirmed(preview):
    new_path = core.renaming.run(preview)               # select it in the GUI
```

**Two kinds of change to the disk:**

| | Renaming a folder | Carrying files into another area |
|---|---|---|
| What happens | One directory entry changes; no data moves | Each file is copied, checked and swapped in; the source is removed |
| How | One kernel call (`os.rename`), atomic | Many steps per file, across drives |
| Duration | Instant | Long: progress, cancel between files |
| Swappable | No reason to | Yes: rclone (scenario 7) |
| Run log | No | Yes, each file |
| Carried out by | `folders`, an infrastructure module | `FileTransfer`, a port |

```python
result = self.transfer.run(plan.moves, watch, run_log)  # Archiving: port
folders.rename(preview.path, preview.new_path)          # Renaming:
                                                        # infrastructure
```

Decided:

- **A clash is a refusal, not a choice.** A batch cannot skip half of its
  own name, so the user has nothing to choose. `prepare` raises
  `NameTaken(path, taken_by)`, as it refuses a path that is not a batch.
- **"Nothing to change" is a normal preview** (`unchanged`), not an error,
  as with an empty publish.
- **The year move is not a line of its own**: the new path shows it.
  Creating a missing year folder is part of carrying out the rename.
- **No fingerprint.** A fingerprint stands in for a plan too large to send;
  rename's whole plan is two paths, and the preview holds them. `run` plans
  again from the preview's own request and compares the plans directly.
- **`run` takes no choice and no watch**: nothing to choose, and one step
  with no progress or stop. It returns the new path, so whatever referred
  to the batch (a GUI selection) can follow it.
- **`batch.renamed(change)` and `Darkroom.path_for(batch)`.** The batch
  owns its name format (Phase 5, scenario 5); the darkroom says where a
  batch belongs, completing the `batch_at` / `path_for` pair (7f). New
  batch will use the same method.
- **The port is `FileTransfer`, not `Mover`.** "Mover" claimed every move
  and then left out the most expected one, a folder to a new name. Named
  after how it works (copy, check, swap in), the port has a boundary its
  users and adapters recognise. `Move` stays as the value object: it is
  the user's intent, and the transfer is one way of carrying it out.
  `MoveResult` became `TransferResult`. Rejected names: `Mover` (claims
  every move), `Copier` (it removes the source), `Courier` or `Carrier`
  (a metaphor to translate).
- **A folder rename is a plain kernel call** in an infrastructure module,
  `folders` (`rename`, later `create` for new batch), not on the port.
  rclone justifies a port for transferring files, not for folder renames;
  on the port, every adapter would carry a method it does not need.
  `folders` hides two OS details: creating a missing parent, and a rename
  that only changes letter case (through a temporary name). Tests use real
  temporary folders.
- **This refines Phase 6's "plan and carry out"**: planning and checking
  stay shared, and how a change is carried out depends on its kind.
- **The app log, not a run log.** A rename either happened or did not, and
  the darkroom view shows which.
- **When rename follows into the showroom and archive** (scenario 4), the
  preview gains `showroom` and `archive` fields (fixed groups, 7c) and
  `run` gains steps across areas. Then a run can stop halfway, and a run
  log earns its place. Only `Renaming` changes.
- A year folder emptied by the move is left in place (walkthrough 4);
  removing it later is one more step in `run`.

## 7h. New batch: assembled from rename's pieces

New batch reuses what rename settled (`path_for`, `folders`, `NameTaken`,
the preview as the whole plan) and adds three small pieces.

**What the user needs to see:**

| Need | Kind | Detail |
|---|---|---|
| Where the new batch will be | Normal | One path, e.g. `Phone/2025/2025-01-03 Lisbon` |
| A new device will be created | Warning | The device name |

```python
class Darkroom:                          # domain service
    def batch_at(self, path: Path) -> Batch: ...
    def path_for(self, batch: Batch) -> Path: ...         # DEVICE/YEAR/BATCH
    def device_named(self, name: str) -> str | None: ...  # existing spelling
    def new_batch_folders(self, batch: Batch) -> list[Path]: ...
                                         # the batch folder and PUBLISH


@dataclass(frozen=True)
class NewBatchPreview:                   # the whole plan
    path: Path                           # where the batch will be
    new_device: bool                     # a warning: a new top folder
    batch: Batch                         # what was asked, to plan again


class StartingBatch:                     # application service
    def prepare(self, device: str, date: BatchDate,
                title: str | None = None) -> NewBatchPreview:
        return self._plan(device, date, title)

    def run(self, preview: NewBatchPreview) -> Path:
        batch = preview.batch
        if self._plan(batch.device, batch.date, batch.title) != preview:
            raise PlanChanged(preview)
        for folder in self.darkroom.new_batch_folders(batch):
            folders.create(folder)                      # infrastructure
        log.info("new batch", path=...)                 # app log
        return preview.path

    def _plan(self, device, date, title) -> NewBatchPreview:
        known = self.darkroom.device_named(device)      # None: a new device
        batch = Batch.new(known or device, date, title) # InvalidName
        path = self.darkroom.path_for(batch)
        # a folder or file with the same name, ignoring case, at the batch,
        # year or device level: NameTaken
        return NewBatchPreview(path, new_device=known is None, batch=batch)
```

On the caller side:

```python
preview = core.starting_batch.prepare("Phone", BatchDate(2025, 1, 3),
                                      "Lisbon")
if not preview.new_device or confirmed(preview):        # GUI: always confirm
    path = core.starting_batch.run(preview)             # select it
```

Decided:

- **New batch shows a preview** (closes the open item in walkthrough 3).
  The user typed everything on it except one consequence: a new device, a
  folder at the top of the darkroom that every device list shows from then
  on. A typo such as `Phnoe` is caught by one confirmation. A new year
  folder is routine and not shown.
- **A device name that matches an existing one ignoring case is that
  device**, not a clash: `phone` means `Phone`, and the batch goes under
  the existing spelling with no warning. The shared same-name rule answers
  "are these the same name?"; each use case decides what that means (a
  clash for files, a refusal for batch names, the same thing for devices).
- **Refusals as in rename**: an unsafe device name is `InvalidName`; a
  batch name taken in that year, or a file where the device or year folder
  must go, is `NameTaken(path, taken_by)`.
- **The batch is the request.** Rename needs `NameChange` because parts
  are kept; here the user describes the whole batch, which owns its name
  format (`Batch.new`).
- **`new_batch_folders(batch)` belongs to the darkroom**: "a new batch gets
  `PUBLISH`" is darkroom layout (Phase 5). The use case does not create
  `publish_folder(batch)` itself, which would encode the layout rule there.
- **`StartingBatch`**: application services are named after the activity,
  and the brief says "start a batch for a device". `CreatingBatch` was
  rejected as technical: every use case creates something.
- **No fingerprint, no watch, no run log**, as in rename: the preview is
  the whole plan, creating folders is one quick step, and it either
  happened or did not.
- New pieces: `folders.create`, `Darkroom.device_named` and
  `Darkroom.new_batch_folders`. Everything else is reused unchanged.
