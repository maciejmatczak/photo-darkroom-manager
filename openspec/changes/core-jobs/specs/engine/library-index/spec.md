# Spec Delta

## MODIFIED Requirements

### Requirement: Scan state is shared
The engine SHALL expose whether a scan is running and whether a scanned
tree is available, to every client. A scan is running while the engine's
job is a scan or refresh that has not finished.

#### Scenario: During a scan
- **WHEN** a full scan is running
- **THEN** every client SHALL see that a scan is running

#### Scenario: After a scan
- **WHEN** a full scan has finished
- **THEN** no scan SHALL be running and a scanned tree SHALL be available

## ADDED Requirements

### Requirement: Library revision
The library SHALL carry a revision number that grows every time any part
of the tree changes, whatever caused it: a scan, a refresh, or the rescan
after an action. Reading nodes SHALL NOT change it.

#### Scenario: Tidy changes the revision
- **WHEN** a client reads revision R and then a tidy finishes and its
  batch is rescanned
- **THEN** the revision SHALL be greater than R

#### Scenario: Reading keeps the revision
- **WHEN** a client reads several nodes
- **THEN** the revision SHALL be unchanged

### Requirement: Changes since a revision
A client SHALL be able to ask which nodes changed since a revision it
read. The engine SHALL return the ids of the subtrees it rescanned or
loaded since then, each re-readable as a whole. When it can no longer tell,
or the tree was dropped, it SHALL return the root.

#### Scenario: One batch rescanned
- **WHEN** a client reads revision R and an archive of one batch then
  finishes and its year is rescanned
- **THEN** the changes since R SHALL be that year's id

#### Scenario: Nothing changed
- **WHEN** a client asks for the changes since the current revision
- **THEN** the answer SHALL be empty

#### Scenario: Darkroom root changed
- **WHEN** a client reads revision R and the darkroom root is then set to
  another folder
- **THEN** the changes since R SHALL be the root
