# Spec Delta

## MODIFIED Requirements

### Requirement: Reading a node
Reading a node by id SHALL return a read-only view of that node and its
whole subtree: id, name, kind, the files directly in the folder, the files
in the whole subtree, the node's own issues, the issues of the whole
subtree, the actions that apply to it, whether the view covers the whole
folder, and its children's views. Changing a returned view SHALL NOT be
possible, and later scans SHALL NOT change a view already returned.

#### Scenario: Batch with a subfolder
- **WHEN** a batch holds one photo and its `PHOTOS` subfolder holds two
- **THEN** the batch view SHALL report one direct photo and three in
  total
- **AND** it SHALL contain the `PHOTOS` view as a child

#### Scenario: View is a snapshot
- **WHEN** a client keeps a view, a photo is added and the node is
  rescanned
- **THEN** the kept view SHALL still report the old counts

## ADDED Requirements

### Requirement: Scoped scan
A client SHALL be able to scan one node by id. The engine SHALL read that
node's subtree and the folders of its ancestors only, and keep every other
part of an already scanned tree as it was. An id that names no library
node, or whose folder does not exist, SHALL be rejected naming the id.

#### Scenario: One batch, nothing scanned before
- **WHEN** no tree is scanned and a client scans
  `Camera/2026/2026-10 Walk`
- **THEN** reading that batch SHALL return its whole subtree
- **AND** no folder of another device SHALL have been read

#### Scenario: Missing folder
- **WHEN** a client scans `Camera/1999` and no such folder exists
- **THEN** the request SHALL be rejected, naming `Camera/1999`

### Requirement: Incomplete ancestors
An ancestor loaded only along the path to a scanned node SHALL report
that its view is incomplete: its children and totals cover only what was
scanned. Scanning that ancestor itself SHALL make it complete.

#### Scenario: Root after scanning one batch
- **WHEN** only `Camera/2026/2026-10 Walk` was scanned and a client reads
  the root
- **THEN** the root view SHALL report that it is incomplete
- **AND** its only descendants SHALL be on the path to that batch

#### Scenario: Full scan completes the tree
- **WHEN** a client then scans the root
- **THEN** the root view SHALL report that it is complete

### Requirement: Resolving a darkroom path
A client SHALL be able to turn a filesystem path inside the darkroom into
a node id. A path outside the darkroom SHALL be rejected with a typed
error naming the path.

#### Scenario: Batch path
- **WHEN** a client resolves `DARKROOM/Camera/2026/2026-10 Walk`
- **THEN** the id SHALL be `Camera/2026/2026-10 Walk`

#### Scenario: Archive path
- **WHEN** a client resolves a path in the archive
- **THEN** the request SHALL be rejected as outside the darkroom

### Requirement: Ids follow on-disk names
An id or path whose folder names differ from the names on disk only in
letter case SHALL address those folders, and the engine SHALL report the
id with the on-disk names. When the case-insensitive match is not unique,
only an exact match SHALL count.

#### Scenario: Lower-case path on a case-insensitive disk
- **WHEN** a client resolves `darkroom/camera/2026/2026-10 walk` and the
  folders are named `Camera` and `2026-10 Walk`
- **THEN** the id SHALL be `Camera/2026/2026-10 Walk`

#### Scenario: Publish folder typed in lower case
- **WHEN** a client addresses `Camera/2026/2026-10 Walk/publish` and the
  folder on disk is `PUBLISH`
- **THEN** the node SHALL be the batch's publish folder
