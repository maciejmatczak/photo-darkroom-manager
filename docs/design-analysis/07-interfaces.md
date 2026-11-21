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
  the plan only if nothing changed. When the preview is the whole plan
  (rename, new batch), the plans are compared directly, with no
  fingerprint (7g).
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
DarkroomPath = NewType("DarkroomPath", PurePosixPath)  # relative: the id

class Darkroom:
    def batch_at(self, path: DarkroomPath) -> Batch: ...  # or refuses
    def publish_folder(self, batch: Batch) -> Path: ...  # full; 7e
    def on_disk(self, path: DarkroomPath) -> Path: ...    # full (7j)

class Showroom:
    def path_for(self, batch: Batch) -> Path: ...  # full path
```

Decided:

- **A caller names a folder by its path inside the darkroom.** A person
  types it in the CLI, a GUI uses it as the id of a node, and it means the
  same in a second process.
- **Two kinds of path, told apart by type** *(Phase 7 review)*:
  - `DarkroomPath` is relative to the darkroom: the id that crosses to and
    from clients. A pure path with forward slashes, so it is the same on
    every OS and in a second process.
  - `Path` is always a full path on disk. Everything that touches physical
    items takes one: `Move`, `folders`, `FileTransfer`, `ExternalApps`.
    `darkroom.on_disk(path)` turns an id into one.
  - `Showroom.path_for` and `Archive.path_for` return full paths. Those
    areas have no ids today; when they are indexed, they get their own
    relative type, and the signatures say which is which.
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
    path: DarkroomPath
    photos: list[Move]
    videos: list[Move]
    clashes: list[TidyClash]
    left_alone: list[LeftAlone]


@dataclass(frozen=True)
class TidyPreview:               # what the user agrees to
    path: DarkroomPath
    photos: int
    videos: int
    clashes: list[TidyClash]
    left_alone: list[LeftAlone]
    fingerprint: str             # of the plan


class Tidying:
    def prepare(self, path: DarkroomPath) -> TidyPreview:
        return TidyPreview.of(self.recipe.plan(path))

    def run(self, preview, choice: StopOrSkip, watch) -> TidyReport:
        plan = self.recipe.plan(preview.path)  # planning again: the check
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
    path: DarkroomPath
    photos_moved: int
    videos_moved: int
    failed: list[Failure]        # file and reason
    skipped: int
    not_reached: int
    stopped: str | None          # "you stopped it", "clashes, as chosen"
    left_alone: list[LeftAlone]
    log: Path | None             # this run's record (7d)
    changed: list[DarkroomPath]  # folders to read again (7i)
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
    source: Path                         # full paths on disk (7b)
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
              path: PurePath) -> ContextManager[RunLogger]: ...
```

The use case:

```python
log = structlog.get_logger(__name__)     # app log: global, classic


class Tidying:                           # application service
    def run(self, preview, choice: StopOrSkip, watch) -> TidyReport:
        plan = self.recipe.plan(preview.path)
        if fingerprint(plan) != preview.fingerprint:
            raise PlanChanged(preview)
        if plan.clashes and choice is StopOrSkip.STOP:
            return TidyReport.stopped_on_clashes(plan)
        with self.run_log.start("tidy", plan.path) as run_log:
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
        log_file = self.folder / f"{stamp()}-{action}.log"
        handler = logging.FileHandler(log_file)   # flushes every line
        base = logging.Logger(f"run.{action}")    # not getLogger: isolated
        base.addHandler(handler)
        try:
            yield RunLogger(structlog.wrap_logger(base), log_file)
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
  | Config | Fixed: a new file, every line flushed | Level and output, set by the client (7k) |

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
- File transfer adapters: `BuiltinTransfer` (copy, verify, swap in;
  named in 8b) and `RcloneTransfer` (Phase 6).

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
    path: DarkroomPath                   # the batch, in the darkroom
    showroom_path: Path
    new: int
    clashes: list[PublishClash]          # a warning; no moves inside
    left_alone: list[LeftAlone]
    fingerprint: str                     # of the plan


@dataclass(frozen=True)
class PublishReport:
    path: DarkroomPath
    showroom_path: Path
    published: int
    replaced: int
    failed: list[Failure]
    skipped: int
    not_reached: int
    stopped: str | None
    left_alone: list[LeftAlone]
    log: Path | None
    changed: list[DarkroomPath]          # the batch (7i)
```

```python
class Publishing:                        # application service
    def prepare(self, path: DarkroomPath) -> PublishPreview:
        return PublishPreview.of(self._plan(path))

    def run(self, preview, choice: StopSkipOrReplace,
            watch) -> PublishReport:
        plan = self._plan(preview.path)
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

    def _plan(self, path: DarkroomPath) -> PublishPlan:
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
    subfolder: PurePosixPath             # "Selects/Day1"; empty: the batch


class Darkroom:                          # domain service
    def batch_at(self, path: DarkroomPath) -> Batch: ...  # or refuses
    def folder_at(self, path: DarkroomPath) -> BatchFolder: ...
    def publish_folder(self, batch: Batch) -> Path: ...  # full


class Showroom:                          # domain service
    def path_for(self, batch: Batch) -> Path: ...  # full path


class Archive:                           # domain service
    def path_for(self, folder: BatchFolder) -> Path: ...  # full path
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
    path: DarkroomPath                   # in the darkroom
    archive_path: Path
    moves: list[Move]                    # subfolders kept
    clashes: list[ArchiveClash]
    blockers: list[ArchiveBlocker]


@dataclass(frozen=True)
class ArchivePreview:                    # what the user agrees to
    path: DarkroomPath                   # in the darkroom
    archive_path: Path
    files: int
    clashes: list[ArchiveClash]
    blockers: list[ArchiveBlocker]
    fingerprint: str                     # of the plan


@dataclass(frozen=True)
class ArchiveReport:
    path: DarkroomPath
    archive_path: Path
    archived: int
    failed: list[Failure]
    skipped: int                         # clashes and blocked files
    not_reached: int
    stopped: str | None
    kept_folders: list[Path]             # emptied, but held open elsewhere
    log: Path | None
    changed: list[DarkroomPath]          # the parent folder (7i)
```

**Removing emptied folders goes to the file transfer**, as a second method:

```python
class FileTransfer(Protocol):            # port
    def run(self, moves, watch, run_log) -> TransferResult: ...
    def remove_empty_folders(self, under: Path,
                             run_log) -> list[Path]: ...  # the kept ones


class Archiving:                         # application service
    def prepare(self, path: DarkroomPath) -> ArchivePreview:
        return ArchivePreview.of(self._plan(path))

    def run(self, preview, choice: StopOrSkip, watch) -> ArchiveReport:
        plan = self._plan(preview.path)
        if fingerprint(plan) != preview.fingerprint:
            raise PlanChanged(preview)
        if (plan.clashes or plan.blockers) and choice is StopOrSkip.STOP:
            return ArchiveReport.stopped_on_clashes(plan)
        with self.run_log.start("archive", plan.archive_path) as run_log:
            result = self.transfer.run(plan.moves, watch, run_log)
            kept = self.transfer.remove_empty_folders(
                self.darkroom.on_disk(plan.path), run_log)
        return ArchiveReport.of(plan, result, kept, log=run_log.path)

    def _plan(self, path: DarkroomPath) -> ArchivePlan:
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
  untouched. *Kept here at the Phase 7 review*, although 7g puts folder
  changes in `folders`: this cleanup follows a transfer and is left to
  rclone's own cleanup when rclone transfers. It takes one folder, not a
  planned list: which folders end up empty depends on what moved. Folders
  held open elsewhere are returned and reported; the cleanup may fail
  without anything being wrong.
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
    path: DarkroomPath                   # the batch now
    new_path: DarkroomPath
    change: NameChange

    @property
    def unchanged(self) -> bool:
        return self.new_path == self.path


class Darkroom:                          # domain service
    def batch_at(self, path: DarkroomPath) -> Batch: ...  # or refuses
    def path_for(self, batch: Batch) -> DarkroomPath: ...


class Renaming:                          # application service
    def prepare(self, path: DarkroomPath,
                change: NameChange) -> RenamePreview:
        return self._plan(path, change)

    def run(self, preview: RenamePreview) -> RenameReport:
        if self._plan(preview.path, preview.change) != preview:
            raise PlanChanged(preview)
        old = self.darkroom.on_disk(preview.path)
        new = self.darkroom.on_disk(preview.new_path)
        folders.rename(old, new)                        # infrastructure
        log.info("renamed", path=..., new_path=...)     # app log
        return RenameReport(new_path=preview.new_path,
                            changed=[...])  # old and new year (7i)

    def _plan(self, path: DarkroomPath,
              change: NameChange) -> RenamePreview:
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
    report = core.renaming.run(preview)          # select report.new_path
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
folders.rename(old, new)                                # Renaming:
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
  to the batch (a GUI selection) can follow it, and the folders it changed
  (a `RenameReport`, 7i).
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
  The line is drawn by what the change belongs to: a folder change on its
  own goes to `folders`; removing the folders a transfer emptied is part of
  the transfer (7f), so rclone can do it with its own cleanup.
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
    def batch_at(self, path: DarkroomPath) -> Batch: ...
    def path_for(self, batch: Batch) -> DarkroomPath: ...
    def device_named(self, name: str) -> str | None: ...  # existing spelling
    def new_batch_folders(self, batch: Batch) -> list[Path]: ...  # full
                                         # the batch folder and PUBLISH


@dataclass(frozen=True)
class NewBatchPreview:                   # the whole plan
    path: DarkroomPath                   # where the batch will be
    new_device: bool                     # a warning: a new top folder
    batch: Batch                         # what was asked, to plan again


class StartingBatch:                     # application service
    def prepare(self, device: str, date: BatchDate,
                title: str | None = None) -> NewBatchPreview:
        return self._plan(device, date, title)

    def run(self, preview: NewBatchPreview) -> NewBatchReport:
        batch = preview.batch
        if self._plan(batch.device, batch.date, batch.title) != preview:
            raise PlanChanged(preview)
        for folder in self.darkroom.new_batch_folders(batch):
            folders.create(folder)                      # infrastructure
        log.info("new batch", path=...)                 # app log
        return NewBatchReport(path=preview.path,
                              changed=[...])  # the year, or the darkroom
                                              # for a new device (7i)

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
    report = core.starting_batch.run(preview)           # select report.path
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

## 7i. See: a query, and a tree the client owns

See only reads: no preview, no plan, no `run`. Its shape comes from the
clients instead: a GUI keeps a tree on screen and refreshes parts of it; a
CLI prints it once.

**What the user needs to see, for each folder:**

| Need | Detail |
|---|---|
| Its name and kind | Device, year, batch, `PUBLISH`, bucket, subfolder, unrecognised |
| Its counts | Photos, videos, other: directly in it, and in total below it |
| Attention | Untidy here, or somewhere below |
| What can be done | Fixed by its kind |

An unrecognised folder shows its name and kind only: no counts, and it is
not walked into (walkthrough 2).

```python
@dataclass(frozen=True)
class Counts:                            # value object
    photos: int
    videos: int
    other: int


@dataclass(frozen=True)
class FolderView:                        # value object: one node of the tree
    path: DarkroomPath                   # the id (7b)
    kind: FolderKind                     # .allows: what can be done
    here: Counts | None                  # None: unrecognised
    total: Counts | None                 # this folder and below
    untidy: bool                         # here
    needs_attention: bool                # here or below
    children: tuple[FolderView, ...]

    def replaced(self, part: FolderView) -> FolderView: ...
        # the same tree with `part` swapped in at its path, totals and
        # attention added up again along the way


class Overview:                          # application service, a query
    def darkroom(self) -> FolderView: ...            # the whole tree
    def folder(self, path: DarkroomPath) -> FolderView: ...
```

Every report says which folders it changed:

```python
@dataclass(frozen=True)
class TidyReport:
    ...
    changed: list[DarkroomPath]          # read these folders again
```

On the caller side:

```python
view = core.overview.darkroom()                       # GUI, at start

report = core.tidying.run(preview, choice, watch)
for path in report.changed:
    view = view.replaced(core.overview.folder(path))  # only those parts

print_tree(core.overview.darkroom())                  # CLI, or .folder(p)
```

Decided:

- **The tree is an immutable value, and the totals rule stays in it.**
  "How counts and attention marks add up the tree" is a domain rule; a GUI
  that refreshed one folder and summed the ancestors itself would hold it.
  `replaced(part)` rebuilds the totals in the core while the client holds
  the tree.
- **The use case says what changed**, in its report's `changed`: tidy the
  folder, publish the batch, archive the parent, rename the old and the new
  year, new batch the year (or the darkroom when a device is new). Named
  `changed`, not `stale`: it states a fact about the disk; "stale"
  describes the client's copy, which the core does not know. Rename and new
  batch therefore return a small report, not a bare path (7g, 7h).
- **The core holds no tree between calls.** A core that cached the view
  and patched it after each run would be stateful, give the GUI and CLI
  different lifetimes to worry about, and bring a stale cache with it. The
  GUI owns what it shows; the core reads the disk each time and does the
  arithmetic. Half of the client-lifetime question is answered: nothing in
  the core goes stale between calls. Rebuilding after settings change is
  the other half *(closed in 7k)*.
- **What a kind allows is a property of the kind** (`FolderKind.allows`),
  a fixed domain table: clients enable menus from it and never hard-code
  it. Kind, not state (walkthrough 2).
- **`Overview`**: the brief's own word ("no overview of what is untidy").
  A query is named by what it gives, not by an activity. Rejected:
  `Seeing` (reads oddly), `DarkroomView` (the result, not the service),
  `Browsing` (a GUI word; the CLI does not browse).
- Commands and queries differ in shape because their problems differ:
  commands need a preview, a plan and a check before acting; a query needs
  a result that is cheap to refresh in parts.

## 7j. Cull, edit and open: a folder opened in another program

All three hand a folder to another program and read nothing back: no
preview, no plan, no report, nothing changed on disk.

**What the user needs to see:**

| Need | When |
|---|---|
| Nothing; the program starts | Normal |
| Disabled | Cull or edit not configured: known before asking, for every client |
| Why it cannot start | A broken template, or no image found |
| That the program failed | It did not start, or exited with an error at once |

**The port knows no templates.** Which tokens exist and how a template is
rendered for a folder is domain knowledge; how to start a program or the
file manager is the OS's (Phase 5). The use case renders the command; the
port is handed something ready to run.

```python
@dataclass(frozen=True)
class CommandTemplate:                   # value object (domain)
    text: str                            # 'frv.exe "{{ folder }}"'

    @property
    def tokens(self) -> set[str]: ...    # TemplateBroken on an unknown one
    def render(self, values: dict[str, Path]) -> str: ...


class ExternalApps(Protocol):            # port
    def start(self, command: str) -> None: ...      # AppFailed
    def show_folder(self, path: Path) -> None: ...  # AppFailed


class Opening:                           # application service
    def in_file_manager(self, path: DarkroomPath) -> None:
        self.apps.show_folder(self.darkroom.on_disk(path))

    def for_culling(self, path: DarkroomPath) -> None:
        self._start(self.settings.cull_command, path)

    def for_editing(self, path: DarkroomPath) -> None:
        self._start(self.settings.edit_command, path)

    @property
    def culling_enabled(self) -> bool:   # and editing_enabled
        return self.settings.cull_command is not None

    def _start(self, template: CommandTemplate | None,
               path: DarkroomPath) -> None:
        if template is None:
            raise NotConfigured
        values = {"folder": self.darkroom.on_disk(path)}
        if "first_image" in template.tokens:
            values["first_image"] = self._first_image(path)  # NoImageFound
        self.apps.start(template.render(values))

    def _first_image(self, path: DarkroomPath) -> Path: ...
        # a best guess: directly in the folder, then in its PHOTOS
```

On the caller side:

```python
core.opening.in_file_manager(folder.path)
if folder.kind.allows(CULL) and core.opening.culling_enabled:
    core.opening.for_culling(folder.path)              # NoImageFound, ...
```

Decided:

- **One port, two methods.** The cull app, the edit app and the file
  manager share a role (Phase 2), so they share a port. Only `start` takes
  a user-given command; `show_folder` hides the OS's file manager
  (`explorer`, `open`, `xdg-open`). `start` also hides how a command string
  is split into arguments on each OS, and how long to wait to catch "exits
  with an error straight away". Tests use a fake that records commands.
- **The first image is looked up only when the template asks for it.**
  Otherwise a template with only `{{ folder }}` would refuse on a folder
  without images, for something it never needed.
- **The first-image guess stays with the use case** (Phase 5): a policy
  for cull and edit, not a layout rule, independent of the tidy recipe.
- **Disabled is a property** (`culling_enabled`, `editing_enabled`), known
  before asking; `NotConfigured` is only a guard. Clients combine it with
  `FolderKind.allows`: the kind says whether it makes sense here, the
  settings whether it is set up.
- **`darkroom.on_disk(path)`** turns a path in the darkroom (7b) into the
  full path an outside program needs; the darkroom knows its root.
- **One service, `Opening`.** Each of the three opens a folder in a
  program; "open" is walkthrough 8's word and the user's. The activity is
  the class, and the methods say where or what for. A hard name was first
  checked as a grouping smell: cull and edit share everything, open shares
  the port, and a service of its own for open would be one call. Rejected:
  `Handoff` (not the user's word), `Culling`, `Editing` and `Opening` as
  three services (one flow), `Tools` (says nothing). Considered:
  `ExternalApps` as the service name, after the outside system the three
  use cases serve; kept for the port, so one word does not name both the
  use case and the system it talks to.
- **Known limit**: token values go into the command as they are, and
  quoting is the template author's. On Windows a path cannot contain `"`;
  on Unix a folder name with a quote breaks the command. A candidate for
  Phase 9.

## 7k. Set up, settings storage, and rebuilding the core

**What the user needs to see:**

| Need | Kind | Detail |
|---|---|---|
| Not set up yet | Normal, first run | One message |
| Ready or not | Normal | One state |
| What is wrong with a required setting | Exception | Per setting: missing, not a folder, overlapping |
| What is wrong with an optional setting | Warning | Per command: why it cannot be rendered |

```python
@dataclass(frozen=True)
class Settings:                          # value object (domain)
    darkroom: Path
    showroom: Path
    archive: Path
    cull_command: CommandTemplate | None = None
    edit_command: CommandTemplate | None = None
    transfer: TransferKind = TransferKind.INTERNAL   # or RCLONE (Phase 6)


class SettingsStore(Protocol):           # port
    def load(self) -> Settings | None: ...           # None: not set up
    def save(self, settings: Settings) -> None: ...


@dataclass(frozen=True)
class SetupState:                        # what the user sees
    ready: bool
    problems: dict[Setting, str]         # required: why not ready
    warnings: dict[Setting, str]         # optional: works without them


class SettingUp:                         # application service
    def current(self) -> Settings | None: ...        # to fill the form
    def check(self, settings: Settings) -> SetupState: ...
    def store(self, settings: Settings) -> SetupState: ...  # AreasOverlap
```

The adapter is a TOML file in the user's config folder (`platformdirs`).

The composition root, shared by both clients. *Corrected in 8c*: the
client first built `TomlSettingsStore` itself, which let a frontend import
an adapter; `open_setup()` builds it inside the core.

```python
setting_up = open_setup()               # builds TomlSettingsStore inside
                                        # works before set up
settings = setting_up.current()
state = setting_up.check(settings) if settings else NOT_SET_UP
core = build_core(settings) if state.ready else None
```

In the GUI, after the user saves:

```python
state = setting_up.store(new_settings)
if state.ready:
    core = build_core(new_settings)                  # a new core
    view = core.overview.darkroom()                  # and a new view (7i)
```

The CLI runs one process per command: it builds once and never rebuilds.

Decided:

- **`store` refuses only overlapping areas** (critical, walkthrough 1). A
  missing folder is stored and reported "not ready": the showroom and
  archive live on a NAS that is sometimes offline, which must not stop the
  user from configuring. The app is ready once the NAS is back.
- **A settings change means a new core.** Designed twice:

  | Option | How | Verdict |
  |---|---|---|
  | A shared, mutable "current settings" read by every service on each call | Nothing to rebuild | Rejected: a run during a darkroom change would read two roots |
  | The core is immutable once built; `build_core(settings)` again | The client swaps its `core` | Chosen |

  "Nothing learned about the old darkroom applies any more" (walkthrough
  1, step 10) holds by construction: nothing survives the rebuild. A run
  in progress keeps its old core and finishes consistently. With 7i (no
  view held between calls), this closes the client-lifetime question.
- **`SettingUp` lives outside the core it builds.** It needs only the
  store and the checks, not the areas, so it works before set up, and the
  first run can say "not set up yet" instead of failing. Its lifetime is
  the process; the core's is one version of the settings (the test of 7d).
- **Loading the devices leaves set up** (walkthrough 1, step 6): the
  darkroom reads its top folders when it needs them (`device_named`, 7h);
  the core keeps nothing between calls.
- **The log level is not a setting** (the parked item). It belongs to the
  client: a CLI flag, or a GUI menu that changes it at runtime. A client
  that remembers it keeps its own preference; the core's `Settings` holds
  only what the core needs.
- **The rclone choice is a setting** (`transfer`); `build_core` picks the
  `FileTransfer` adapter from it, the one place a setting chooses an
  adapter (scenario 7).
- **`SettingUp`, not `SettingsService`.** A `Service` suffix names the
  pattern, which every application service shares, so it tells nothing
  apart; next to the `SettingsStore` port, `SettingsService` would blur a
  check-and-refuse use case with a file writer. Services are named after
  the activity (7a; Evans, ch. 5); "set up" is walkthrough 1's title. The
  suffix would be right where it is the team's convention.

## Phase 7 at a glance

Collected from 7a-7k after the review; where a checkpoint's sketch and
this list differ, this list holds. `DarkroomPath` is the relative id;
`Path` is a full path on disk (7b). Adapter names follow Phase 8b; where
each piece lives is in [08-structure.md](08-structure.md).

**Application services** (the use cases):

| Service | Calls | Checkpoint |
|---|---|---|
| `Tidying` | `prepare(path) -> TidyPreview`; `run(preview, StopOrSkip, watch) -> TidyReport` | 7c, 7d |
| `Publishing` | `prepare(path) -> PublishPreview`; `run(preview, StopSkipOrReplace, watch) -> PublishReport` | 7e |
| `Archiving` | `prepare(path) -> ArchivePreview`; `run(preview, StopOrSkip, watch) -> ArchiveReport` | 7f |
| `Renaming` | `prepare(path, NameChange) -> RenamePreview`; `run(preview) -> RenameReport` | 7g |
| `StartingBatch` | `prepare(device, date, title) -> NewBatchPreview`; `run(preview) -> NewBatchReport` | 7h |
| `Overview` | `darkroom() -> FolderView`; `folder(path) -> FolderView` | 7i |
| `Opening` | `in_file_manager(path)`; `for_culling(path)`; `for_editing(path)`; `culling_enabled`; `editing_enabled` | 7j |
| `SettingUp` | `current()`; `check(settings) -> SetupState`; `store(settings) -> SetupState` | 7k |

**Domain services:**

| Service | Calls | Checkpoint |
|---|---|---|
| `Darkroom` | `batch_at(path) -> Batch`; `folder_at(path) -> BatchFolder`; `path_for(batch) -> DarkroomPath`; `on_disk(path) -> Path`; `publish_folder(batch) -> Path`; `device_named(name)`; `new_batch_folders(batch) -> list[Path]` | 7b, 7f, 7g, 7h, 7j |
| `Showroom` | `path_for(batch) -> Path` | 7b |
| `Archive` | `path_for(folder) -> Path` | 7f |
| The tidy recipe | `plan(path) -> TidyPlan` | 7c |

**Ports and their adapters:**

| Port | Calls | Adapters | Checkpoint |
|---|---|---|---|
| `FileTransfer` | `run(moves, watch, run_log) -> TransferResult`; `remove_empty_folders(under, run_log) -> list[Path]` | `BuiltinTransfer`, `RcloneTransfer` | 7d, 7f, 7g |
| `RunLog` | `start(action, path) -> RunLogger` (a context manager) | `FileRunLog` | 7d |
| `ExternalApps` | `start(command)`; `show_folder(path)` | `OsExternalApps` | 7j |
| `SettingsStore` | `load() -> Settings or None`; `save(settings)` | `TomlSettingsStore` | 7k |

Infrastructure without a port: `folders` (`rename`, `create`), and the app
log (`structlog.get_logger(__name__)`). Composition root: `open_setup()`
and `build_core(settings) -> Core`, the latter called again after a
settings change (7k, 8c).

**Value objects:** `DarkroomPath`, `Batch`, `BatchDate`, `BatchFolder`,
`NameChange`, `Move`, `TransferResult`, `Failure`, `LeftAlone`,
`TidyClash`, `PublishClash`, `ArchiveClash`, `ArchiveBlocker`, `Counts`,
`FolderView`, `FolderKind`, `CommandTemplate`, `Settings`, `SetupState`,
the choices `StopOrSkip` and `StopSkipOrReplace`, and each use case's plan,
preview and report.

**The client passes in:** a `RunWatch` (`progress`, `cancelled`).

**Refusals** (raised before anything changes):

| Refusal | Raised by | Checkpoint |
|---|---|---|
| `NotABatch` | `Darkroom.batch_at`, `Darkroom.folder_at` | 7b, 7f |
| `PlanChanged` | Every `run`, when planning again differs | 7a |
| `NameTaken(path, taken_by)` | Rename, new batch | 7g, 7h |
| `InvalidName` | New batch (an unsafe device name) | 7h |
| `NotConfigured`, `TemplateBroken`, `NoImageFound` | Opening | 7j |
| `AppFailed` | `ExternalApps` | 7j |
| `AreasOverlap` | `SettingUp.store` | 7k |
