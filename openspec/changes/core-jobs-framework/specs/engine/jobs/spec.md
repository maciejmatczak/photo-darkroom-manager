# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
