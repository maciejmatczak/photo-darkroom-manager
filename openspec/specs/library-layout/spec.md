# library-layout Specification

## Purpose

Defines the photo library domain: the roles of the darkroom, archive, and
showroom roots and how content flows between them; the device-first darkroom
layout and batch-first archive and showroom layouts; reversible path translation
between areas; batch and device naming rules; and recognizing which batch a
darkroom path belongs to.

## Requirements

### Requirement: Library roots
The library SHALL consist of three configured roots with distinct roles:
the darkroom holds active work, the archive holds finished source
material, and the showroom holds published results. Content SHALL flow
from darkroom to archive and from darkroom to showroom, never back.

#### Scenario: Roots are independent
- **WHEN** a batch exists in darkroom, archive, and showroom
- **THEN** each copy SHALL be located by its own root and layout

### Requirement: Darkroom layout
The darkroom SHALL be organized device-first as
`DARKROOM/DEVICE/YEAR/BATCH/`. A batch MAY contain `PUBLISH/`, loose
files, subfolders, and the media buckets `PHOTOS/` and `VIDEOS/`.

#### Scenario: Batch location
- **WHEN** device Camera has batch `2026-10 Walk`
- **THEN** it SHALL be located at `DARKROOM/Camera/2026/2026-10 Walk/`

### Requirement: Archive and showroom layout
The archive and showroom SHALL be organized batch-first as
`ROOT/YEAR/BATCH/DEVICE/`. Devices with the same year and batch SHALL
share the batch folder and keep separate device folders.

#### Scenario: Two devices share a batch
- **WHEN** Camera and Phone both have batch `2026/2026-10 Walk`
- **THEN** their destinations SHALL be `2026/2026-10 Walk/Camera` and
  `2026/2026-10 Walk/Phone`

### Requirement: Path translation between areas
A path SHALL be translated from one area (darkroom, archive, showroom) to
another given only the source and target area. Each area's layout SHALL
be determined by the area itself; callers SHALL NOT specify layouts.
Translation SHALL reorder the device, year, and batch components as the
layouts require and preserve every trailing component. It SHALL be
reversible, SHALL NOT touch the filesystem, and SHALL NOT require either
path to exist.

#### Scenario: Darkroom to archive
- **WHEN** `DARKROOM/Camera/2026/2026-10 Walk/PHOTOS/x.raw` is translated
  from darkroom to archive
- **THEN** the result SHALL be
  `ARCHIVE/2026/2026-10 Walk/Camera/PHOTOS/x.raw`
- **AND** translating it back to darkroom SHALL return the original path

#### Scenario: Between areas with the same layout
- **WHEN** a showroom path is translated to archive
- **THEN** only the root SHALL change

#### Scenario: Unsafe path rejected
- **WHEN** the path is outside the source root, has fewer than three
  relative components, or contains `..`
- **THEN** translation SHALL raise `ValueError`

### Requirement: Batch name
A batch folder name SHALL follow `YYYY-MM[-DD][ title]`. Day and title
SHALL be optional. A batch replaces the former album concept; its name
MAY be provisional.

#### Scenario: Date-only batch
- **WHEN** the name is `2026-10`
- **THEN** it SHALL be valid

#### Scenario: Invalid shape
- **WHEN** the name does not start with `YYYY-MM`
- **THEN** it SHALL be rejected with a descriptive error

### Requirement: Device name
A device name SHALL be trimmed and SHALL be a safe single directory
component on Windows. Spaces and Unicode letters SHALL be allowed.

#### Scenario: Unsafe names rejected
- **WHEN** the name is blank, `.`, `..`, contains `/`, `\`, `:`, another
  Windows-forbidden or control character, ends with a dot, is a Windows
  reserved name such as `CON` (with or without an extension), or equals
  `PUBLISH`, `PHOTOS`, or `VIDEOS` in any case
- **THEN** it SHALL be rejected

#### Scenario: Safe names accepted
- **WHEN** the name is `Camera`, `My Camera`, or `Aparat Łukasza`
- **THEN** it SHALL be accepted

### Requirement: Batch recognition
Given a darkroom path, the system SHALL identify its device, year, batch,
batch path, and relative subpath. A batch's publish folder SHALL be
`BATCH/PUBLISH`.

#### Scenario: Path inside a batch
- **WHEN** `DARKROOM/Camera/2026/2026-10 Walk/PHOTOS` is recognized
- **THEN** device SHALL be `Camera`, year `2026`, batch `2026-10 Walk`

#### Scenario: Too shallow
- **WHEN** the path is the root, a device, or a year folder
- **THEN** no batch SHALL be recognized
