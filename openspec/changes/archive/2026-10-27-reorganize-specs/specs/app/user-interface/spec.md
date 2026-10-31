# Spec Delta

## Purpose

Defines the darkroom user interface: Batch terminology, which actions each kind
of tree row offers, the New Batch form and its device selection, and how the tree
reflects changes.

## ADDED Requirements

### Requirement: Batch terminology
All UI text, previews, help, and log fields SHALL use Batch instead of
Album.

#### Scenario: Toolbar
- **WHEN** the main page is shown
- **THEN** the toolbar SHALL offer New Batch

### Requirement: Device and year rows
Device and year rows SHALL offer Open in Explorer, counts, issues, and
expand/collapse, and SHALL NOT offer batch actions or destination links.
Device rows SHALL additionally offer New Batch for that device.

#### Scenario: New Batch from a device row
- **WHEN** the user starts New Batch from the Camera device row
- **THEN** the form SHALL open with Camera preselected

#### Scenario: Year row controls
- **WHEN** a year row is rendered
- **THEN** it SHALL show no New Batch, publish, archive, rename, or
  destination link controls

### Requirement: Batch and subfolder rows
Batch rows SHALL expose every action former album rows exposed.
Subfolder and `PUBLISH` rows SHALL keep their action gates. Archive and
showroom Open buttons SHALL open the same destination the archive
or publish action uses, and stay enabled only when that folder exists.

#### Scenario: Subfolder showroom link
- **WHEN** a subfolder row is rendered
- **THEN** its showroom link SHALL keep its existing behavior, even if no
  published subfolder exists

### Requirement: New Batch form
The form SHALL load device choices when it opens, require an explicit
device (existing or typed custom name), and keep current date defaults.
Opened from the toolbar, it SHALL preselect no device; opened from a
device row, it SHALL preselect that device and still allow changing it.

#### Scenario: Blank device
- **WHEN** the user submits without choosing a device
- **THEN** no batch SHALL be created

### Requirement: Rows appear after creation
After a batch is created, its rows SHALL appear in the tree without a manual
refresh, including any new device or year row it required.

#### Scenario: First batch for a new device
- **WHEN** a batch is created under a new device
- **THEN** the device, year, and batch rows SHALL appear
