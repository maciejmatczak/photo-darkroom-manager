# engine/planned-actions Specification

## Purpose

Defines how a client prepares a planned action into a plan, shows it,
answers its questions and executes it, so every client follows the same
form-like flow and every planned action runs the same way.

## Requirements

### Requirement: Planned actions
Rename, new batch, tidy, archive and publish SHALL be planned actions: a
client SHALL first prepare one, with the action's own inputs, and then
execute the plan it got. Preparing SHALL change nothing.

#### Scenario: Prepare a rename
- **WHEN** a client prepares renaming `Camera/2026/2026-10 Walk` with the
  title `Hike`
- **THEN** the client SHALL get a plan
- **AND** no folder SHALL be renamed

### Requirement: Preparing yields a plan or a refusal
Preparing SHALL either return a plan or be refused with a typed error
carrying a message. When there is nothing to do, preparing SHALL still
return a plan, which SHALL say so. Each planned action SHALL have its own
kind of plan, which
describes what will happen in that action's own terms; there SHALL be no
generic preview shared by all actions. Every plan SHALL also carry the
action's questions for the user and a fingerprint, and handing a plan
back SHALL be enough to execute it.

#### Scenario: Rename plan
- **WHEN** a client prepares renaming `2026-10 Walk` to `2026-10-05 Walk`
- **THEN** the plan SHALL name the old and the new folder

#### Scenario: Archive plan
- **WHEN** a client prepares archive of a batch of 100 files, 10 of them
  already in the archive
- **THEN** the plan SHALL name where the batch goes, the 100 files and
  the 10 already archived

#### Scenario: Nothing to tidy
- **WHEN** a client prepares tidy of a batch with no misplaced files
- **THEN** preparing SHALL return a plan that says there is nothing to do

#### Scenario: Name already taken
- **WHEN** a client prepares renaming a batch to a name another batch of
  that year already has
- **THEN** preparing SHALL be refused, naming the folder
- **AND** no plan SHALL be returned

### Requirement: Plans ask the action's own questions
A plan SHALL list what the user must decide before it runs, as questions
the action defines, each with its choices and, where the action has one,
a default. A plan without questions SHALL need only a confirmation. What
a question means SHALL be known only to its action and the client that
shows it.

#### Scenario: Republish asks about existing files
- **WHEN** a client prepares publishing a batch whose 3 of 10 files
  already exist in the showroom
- **THEN** the plan SHALL ask whether to replace or skip those files

#### Scenario: Archive with nothing in the way
- **WHEN** a client prepares archive of a batch none of whose files exist
  in the archive
- **THEN** the plan SHALL ask no questions

### Requirement: Plans carry a fingerprint
Each plan SHALL carry a short fingerprint derived from what the action
plans to do and its questions.
Preparing the same action against the same disk and configuration SHALL
give the same fingerprint, in any process; any change in what the action
plans or asks SHALL give a different one. The engine SHALL NOT store
plans or fingerprints.

#### Scenario: Same preparation twice
- **WHEN** a client prepares archive of a batch twice with no change on
  disk
- **THEN** both plans SHALL carry the same fingerprint

#### Scenario: File added in between
- **WHEN** a file is added to the batch between two preparations
- **THEN** the two fingerprints SHALL differ

### Requirement: Executing a plan
A client SHALL execute a plan by handing it back, with its answers, to
that action's own execute call; each planned action SHALL have its own
call, and a plan SHALL be accepted only by its action's call. The action
SHALL be prepared again from the plan, and executed only when the new
plan has the same fingerprint. Otherwise executing SHALL be refused with a typed
error reporting the plan's and the current fingerprint, before any job
starts, and no file SHALL change.

#### Scenario: Plan changed since the preview
- **WHEN** a client was shown an archive plan, a file was then added to
  the batch, and the client executes that plan
- **THEN** executing SHALL be refused, reporting both fingerprints
- **AND** no job SHALL start and no file SHALL be moved

#### Scenario: Plan unchanged
- **WHEN** nothing changed since the preview and the client executes the
  plan
- **THEN** the action SHALL be executed

### Requirement: Answers are checked before running
An answer SHALL be one of its question's choices; a question left
unanswered SHALL take its default. A missing answer to a question without
a default, an unknown question or a choice the question does not offer
SHALL refuse the execution with a typed error naming the question, before
any job starts, and no file SHALL change.

#### Scenario: Republish without a choice
- **WHEN** a client executes a republish plan that asks about existing
  files and gives no answer
- **THEN** executing SHALL be refused, naming that question
- **AND** no job SHALL start and no file SHALL be published

#### Scenario: Republish with replace
- **WHEN** the client answers that question with replace
- **THEN** the new files SHALL be put in place of the old ones

### Requirement: Answers cover what the run finds
When the action finds, while running, a situation one of its questions
covered, it SHALL follow the user's answer to that question.

#### Scenario: Late file in the archive with skip
- **WHEN** a file appears in the archive at a planned target after the
  preview and the archive runs with the answer to skip existing files
- **THEN** that file SHALL be skipped and reported
- **AND** the other planned files SHALL be archived

### Requirement: A planned action runs as a job
Executing a plan that passed its checks SHALL start a job and return at
once; the job's result SHALL carry the action's result. The job SHALL
report progress where the action can count its work, and SHALL write the
job's log.

#### Scenario: Rename is a job
- **WHEN** a client executes a rename plan
- **THEN** the engine's job SHALL be that rename until it finishes
- **AND** its result SHALL carry the renamed node

### Requirement: Execution follows the plan
Executing a plan SHALL do only what its plan described. It SHALL NOT
move, create or rename anything the plan did not cover.

#### Scenario: Late file in a tidy folder
- **WHEN** a misplaced file appears in a batch after its tidy plan was
  prepared and the plan is executed
- **THEN** the new file SHALL stay where it is

### Requirement: Results report what the action did
An execution result SHALL carry its outcome (`ok`, `failed` or
`cancelled`), a message and the action's own report of what it did. Each
planned action SHALL have its own kind of result; what it reports SHALL
be up to that action.

#### Scenario: Rename result
- **WHEN** a rename plan has been executed
- **THEN** its result SHALL carry an `ok` outcome and say the new folder
  name
