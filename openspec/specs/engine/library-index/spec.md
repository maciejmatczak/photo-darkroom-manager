# engine/library-index Specification

## Purpose
Defines how clients address, scan and read the library tree the engine
holds, what a node's view contains, and when the scanned tree is dropped.

## Requirements

### Requirement: Node identity
Each node SHALL be addressed by an id: its path relative to the darkroom
root, written with forward slashes; the root's id SHALL be empty. A node's
id SHALL stay the same across rescans as long as its folder keeps its
path. Clients SHALL address nodes only by id.

#### Scenario: Batch id
- **WHEN** the darkroom contains `Camera/2026/2026-10 Walk`
- **THEN** that batch's id SHALL be `Camera/2026/2026-10 Walk`

#### Scenario: Id survives a rescan
- **WHEN** a client reads a batch, rescans its device and reads the same
  id again
- **THEN** it SHALL get the same batch

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

### Requirement: Reading before a scan or an unknown id
Reading a node SHALL be rejected with a typed error when the tree has not
been scanned, or when the id is not in the tree, naming the id.

#### Scenario: Not scanned yet
- **WHEN** a client reads the root before any scan
- **THEN** the request SHALL be rejected as not scanned

#### Scenario: Unknown id
- **WHEN** a client reads `Camera/1999` and no such node is in the tree
- **THEN** the request SHALL be rejected, naming `Camera/1999`

### Requirement: Scan state is shared
The engine SHALL expose whether a scan is running and whether a scanned
tree is available, to every client.

#### Scenario: During a scan
- **WHEN** a full scan is running
- **THEN** every client SHALL see that a scan is running

#### Scenario: After a scan
- **WHEN** a full scan has finished
- **THEN** no scan SHALL be running and a scanned tree SHALL be available

### Requirement: New darkroom root drops the tree
Setting a different darkroom root SHALL drop the scanned tree, so no
client can read nodes of the old root; clients scan again to get the new
one.

#### Scenario: Darkroom moved in settings
- **WHEN** the tree was scanned and a client sets a different darkroom
  root
- **THEN** no scanned tree SHALL be available
- **AND** reading the root SHALL be rejected as not scanned

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
