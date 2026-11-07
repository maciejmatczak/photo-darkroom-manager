# Spec Delta

## MODIFIED Requirements

### Requirement: Preview by default
Without `--apply` or `--confirm`, a command for an action that changes
files SHALL print its summary of intent, its conflicts, the plan's
fingerprint and the command that confirms it, and change nothing. An
action that changes no files SHALL run at once.

#### Scenario: Archive preview
- **WHEN** a user runs `darkroom archive .` inside a batch
- **THEN** the files to move, `plan` with the fingerprint, and the
  `--confirm` command SHALL be printed
- **AND** no file SHALL be moved

#### Scenario: Open runs at once
- **WHEN** a user runs `darkroom open .`
- **THEN** the folder SHALL open without `--apply` or `--confirm`

#### Scenario: Preview with conflicts
- **WHEN** a user previews archive of a batch with 10 files already in
  the archive
- **THEN** the preview SHALL count the 10 conflicts and list them
- **AND** the printed `--confirm` command SHALL carry the conflict option
  the user gave, if any

### Requirement: Exit codes
The exit code SHALL be 0 for ok, no-op and a printed preview; 1 for
failed; 2 for a usage error; 3 for refused, including not allowed, busy,
a refused conflict and an ambiguous target; 4 when the engine is not
ready; 5 when the target is not found or outside the darkroom; and 130
when the user cancelled the job.

#### Scenario: Archive a year
- **WHEN** a user runs `darkroom archive "id:Camera/2026"`
- **THEN** the exit code SHALL be 3

#### Scenario: Unknown id
- **WHEN** a user runs `darkroom inspect "id:Camera/1999"` and no such
  folder exists
- **THEN** the exit code SHALL be 5

#### Scenario: Conflicts without an option
- **WHEN** a user runs `darkroom archive . --apply` and some files are
  already in the archive
- **THEN** the exit code SHALL be 3 and no file SHALL be moved

## ADDED Requirements

### Requirement: Conflict option
Commands for actions that can have conflicts SHALL accept
`--on-conflict skip`, and `publish` SHALL also accept
`--on-conflict replace`. Without the option, conflicts SHALL refuse the
command. A value the action does not support SHALL be a usage error.

#### Scenario: Archive skipping conflicts
- **WHEN** a user runs `darkroom archive . --apply --on-conflict skip`
  and 10 of 100 files are already in the archive
- **THEN** 90 files SHALL be archived and the 10 reported as skipped

#### Scenario: Replace on archive
- **WHEN** a user runs `darkroom archive . --on-conflict replace`
- **THEN** the command SHALL fail as a usage error

### Requirement: Progress while a job runs
While a job runs, the tool SHALL show its progress on stderr when stderr
is a terminal, and show nothing extra otherwise. Stdout SHALL carry only
the final result, in text or JSON.

#### Scenario: Agent run
- **WHEN** an agent runs `darkroom --json archive . --apply` with stderr
  captured to a file
- **THEN** stdout SHALL be one JSON document with the result
- **AND** no progress lines SHALL be written

### Requirement: Cancel with Ctrl+C
Pressing Ctrl+C while a job runs SHALL cancel the job, wait for it to
stop, print its result like any other result, and exit with code 130.

#### Scenario: Cancel an archive
- **WHEN** a user presses Ctrl+C while `darkroom archive . --apply` runs
- **THEN** the files moved so far SHALL stay archived
- **AND** the output SHALL list what was moved and what was left
