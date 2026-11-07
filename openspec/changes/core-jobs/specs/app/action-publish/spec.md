# Spec Delta

## MODIFIED Requirements

### Requirement: Publish to the device showroom folder
Publishing a batch SHALL move the contents of its `PUBLISH/` directly
into the batch's showroom device folder, as resolved by the library path
mapping. Only the `PUBLISH` component SHALL be stripped. A file already in
the showroom SHALL be replaced only when the user chooses to replace.

#### Scenario: Two devices publish the same batch
- **WHEN** Camera and Phone each publish `2026/2026-10 Walk`
- **THEN** files SHALL land in `SHOWROOM/2026/2026-10 Walk/Camera` and
  `SHOWROOM/2026/2026-10 Walk/Phone` respectively

### Requirement: Overwrites are shown before publishing
The publish preview SHALL list every file that would replace a file
already in the showroom, by name, and count them apart from the new
files.

#### Scenario: Republishing a batch
- **WHEN** `PUBLISH/` holds `a.jpg` and `b.jpg` and the showroom device
  folder already holds `a.jpg`
- **THEN** the preview SHALL list `a.jpg` as replaced and `b.jpg` as new

## ADDED Requirements

### Requirement: Replace or skip existing files
When the showroom already holds some of the files, publishing SHALL be
refused unless the user chooses to replace them or to skip them. Replacing
SHALL put the new files in place of the old ones; skipping SHALL publish
only the new files and leave the others in `PUBLISH/`, reported.

#### Scenario: Replace
- **WHEN** the user republishes the batch above and chooses replace
- **THEN** the showroom SHALL hold the new `a.jpg` and `b.jpg`
- **AND** `PUBLISH/` SHALL be empty

#### Scenario: Skip
- **WHEN** the user republishes the batch above and chooses skip
- **THEN** the showroom SHALL hold its old `a.jpg` and the new `b.jpg`
- **AND** `PUBLISH/` SHALL still hold `a.jpg`

#### Scenario: No choice made
- **WHEN** the user republishes the batch above without choosing
- **THEN** publishing SHALL be refused, listing `a.jpg`
- **AND** no file SHALL move
