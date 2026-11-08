# engine/jobs Specification

## Purpose

Defines the one job the engine runs at a time: how a client starts it,
follows it, waits for it and cancels it, and which work runs as a job, so
every client sees running work the same way.

## Requirements

### Requirement: What runs as a job
The heavy actions that change files (tidy, archive and publish) and every
library scan and refresh SHALL run as a job. All other actions (open,
cull, edit, rename and new batch) SHALL run at once and never as a job.

#### Scenario: Archive is a job
- **WHEN** a client applies archive of a batch
- **THEN** the archive SHALL run as a job of kind archive for that batch

#### Scenario: Opening a folder is not a job
- **WHEN** a client opens a batch's folder
- **THEN** the folder SHALL open and no job SHALL be started

#### Scenario: Rename is not a job
- **WHEN** a client applies rename of a batch
- **THEN** the batch SHALL be renamed and no job SHALL be started
- **AND** the engine's job SHALL be the one it had before, if any

### Requirement: Starting a job returns at once
Starting a job SHALL return before its work is done; the work SHALL run
in the background, and the client SHALL stay free to read the engine
while it runs.

#### Scenario: Reading during an archive
- **WHEN** a client starts archiving a large batch
- **THEN** the start SHALL return while files are still being moved
- **AND** the client SHALL be able to read the library and the job

### Requirement: One job at a time
The engine SHALL hold at most one job. Starting a job while one is `new`,
`running` or `cancelling` SHALL be rejected with a typed busy error naming
the running job. Starting a job after the last one finished SHALL replace
it; the engine SHALL keep no list of past jobs.

#### Scenario: Second job while busy
- **WHEN** a scan is running and a client starts a tidy
- **THEN** the tidy SHALL be rejected as busy, naming the scan

#### Scenario: Next job replaces the finished one
- **WHEN** a tidy has finished and a client starts an archive
- **THEN** the engine's job SHALL be the archive
- **AND** the tidy SHALL no longer be readable from the engine

### Requirement: Reading the job
Every client SHALL be able to read the engine's job as a read-only
snapshot: its kind, node id, state, progress, start and end times, the
path of its log file, and its result once it has finished. With no job
started yet, there SHALL be none.

#### Scenario: Finished job keeps its result
- **WHEN** a tidy has finished
- **THEN** reading the job SHALL give state `done` and the tidy's result

#### Scenario: Snapshot does not change
- **WHEN** a client keeps a snapshot of a running job and the job then
  finishes
- **THEN** the kept snapshot SHALL still show it running

### Requirement: Job states
A job's state SHALL be one of `new` (accepted, not yet running),
`running`, `cancelling` (asked to stop, not stopped yet), `done`,
`failed` and `cancelled`. A job SHALL end in exactly one of the last
three, and a finished job's state SHALL never change.

#### Scenario: Action that fails on a file
- **WHEN** an archive moves some files and fails on one
- **THEN** the job SHALL end `done`
- **AND** its result SHALL have the `failed` outcome and name the file

#### Scenario: Nothing to do
- **WHEN** a tidy job finds nothing to tidy
- **THEN** the job SHALL end `done` with a `noop` result

### Requirement: Progress is optional
A running job SHALL report progress as a count of finished units, a total
when the job knows it, and the item it is working on when it has one. A
job that cannot count SHALL report no total, so a client can show that it
is busy without a percentage.

#### Scenario: Archive progress
- **WHEN** an archive of 40 files has moved 10
- **THEN** its progress SHALL show 10 of 40 and the file being moved

#### Scenario: Scan progress
- **WHEN** a scan is running
- **THEN** its progress SHALL have no total

### Requirement: Waiting for a job
A client SHALL be able to wait for the running job to finish, with or
without a time limit, and get its final snapshot.

#### Scenario: Wait with a limit
- **WHEN** a client waits one second for a job that needs longer
- **THEN** the wait SHALL return with the job still running

### Requirement: Cancelling a job
A client SHALL be able to cancel the running job. The job SHALL stop at
the next point where its work can stop safely, never in the middle of a
file, and end `cancelled`. Cancelling when no job runs SHALL do nothing.

#### Scenario: Cancel an archive
- **WHEN** an archive of 40 files is cancelled after 10 were moved
- **THEN** the job SHALL end `cancelled`
- **AND** its result SHALL list the 10 files moved and the 30 left

#### Scenario: Cancel after the end
- **WHEN** a client cancels a job that already ended `done`
- **THEN** the job SHALL stay `done`

### Requirement: Blocking calls run as jobs
The engine's blocking calls for scanning, refreshing and applying a heavy
action SHALL start a job and wait for it, so they follow the same busy
rule and leave the same job, state and log as a job started directly.

#### Scenario: Blocking scan
- **WHEN** a client calls the blocking scan and it returns
- **THEN** the engine's job SHALL be a finished scan

### Requirement: A job's final state follows from its run
A job's final state SHALL follow from how its work ended, never from the
content of its result: `failed` when the work raised an error,
`cancelled` when a cancel was asked and the work stopped for it, and
`done` otherwise. What the work did to each file SHALL be reported in its
result.

#### Scenario: Work raises an error
- **WHEN** a scan stops because of an unexpected error
- **THEN** the job SHALL end `failed` with the error

#### Scenario: Refused at run time
- **WHEN** a tidy job finds at run time that its conflicts block it and
  moves nothing
- **THEN** the job SHALL end `done` with a `refused` result
