# Spec Delta

## MODIFIED Requirements

### Requirement: Rescan after an action
After the engine executes an action that changes the darkroom, it SHALL
rescan the part of the tree the action affected as part of the same job,
also when the action failed or was cancelled after changing files, and
the result SHALL carry the id it rescanned. When no tree is scanned, it
SHALL rescan nothing and the result SHALL carry no id.

#### Scenario: Tidy updates the tree
- **WHEN** a client executes tidy on an untidy batch
- **THEN** reading that batch afterwards SHALL report no untidy issue
- **AND** the result SHALL carry the id that was rescanned

#### Scenario: Opening an external app
- **WHEN** a client executes an action that opens an external app
- **THEN** the result SHALL carry no rescanned id

#### Scenario: Cancelled archive
- **WHEN** an archive is cancelled after moving some files
- **THEN** reading the batch after the job ends SHALL count only the files
  still in the darkroom

## ADDED Requirements

### Requirement: Cancelled scan keeps the library
Cancelling a scan or refresh SHALL leave the library tree exactly as it was
before that scan started.

#### Scenario: Cancel a full rescan
- **WHEN** a tree is scanned, a batch is added on disk, and a full rescan
  is cancelled before it ends
- **THEN** reading the root SHALL give the same view as before the rescan
- **AND** the new batch SHALL not be in the tree
