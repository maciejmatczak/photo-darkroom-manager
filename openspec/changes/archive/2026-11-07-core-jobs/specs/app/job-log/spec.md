# Spec Delta

## Purpose

Defines the audit log every job leaves on disk, so a user can always find
out afterwards exactly what a job did to their files.

## ADDED Requirements

### Requirement: One log file per job
Every job SHALL write its own log file in a `jobs` folder inside the
application's logs folder. The file name SHALL start with the job's start
date and time and name its kind and node, so that sorting by name sorts by
start time. Two jobs SHALL never share a file.

#### Scenario: Archive log name
- **WHEN** an archive of `Camera/2026/2026-10 Walk` starts on 7 November
  2026 at 14:30:12
- **THEN** its log SHALL be a file in `jobs` whose name starts with
  `2026-11-07_143012` and names `archive` and the batch

### Requirement: The log is complete
A job's log SHALL record the request, the summary of intent the plan
showed, the conflict policy, every step with its result (done, skipped
or failed with the reason), the files left, the refreshed node and the
final state and outcome with the duration. It SHALL hold at least
everything the job reported to the client.

#### Scenario: Partial archive
- **WHEN** an archive skips two conflicting files and moves the rest
- **THEN** the log SHALL list every moved file with its source and
  target, the two skipped files, and the final outcome

#### Scenario: Failed step
- **WHEN** a move fails because the target drive is full
- **THEN** the log SHALL name the file and the reason

### Requirement: The log is written as the job runs
Each step SHALL be in the log when it finishes, not only at the end, so a
job stopped by a crash still shows what it had done.

#### Scenario: App closed mid-job
- **WHEN** the app is killed after an archive moved 10 of 40 files
- **THEN** the archive's log SHALL list the 10 files moved

### Requirement: Job logs are kept
Job logs SHALL NOT be removed by the cleanup of old application logs.

#### Scenario: Old job log
- **WHEN** the app starts and a job log is older than the application log
  retention
- **THEN** the job log SHALL still exist
