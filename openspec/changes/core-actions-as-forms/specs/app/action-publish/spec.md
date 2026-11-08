# Spec Delta

## ADDED Requirements

### Requirement: What can be published
Publishing SHALL take the files directly in the batch's `PUBLISH/`. A
batch without `PUBLISH/`, or whose `PUBLISH/` holds folders, SHALL be
refused at the preview. An empty `PUBLISH/` SHALL be reported as nothing
to do.

#### Scenario: No PUBLISH folder
- **WHEN** a user previews publishing a batch that has no `PUBLISH/`
- **THEN** the preview SHALL be refused, saying `PUBLISH` is missing

#### Scenario: Folder inside PUBLISH
- **WHEN** `PUBLISH/` holds a folder
- **THEN** the preview SHALL be refused and no file SHALL move

#### Scenario: Nothing to publish
- **WHEN** `PUBLISH/` is empty
- **THEN** the preview SHALL say there is nothing to do

## MODIFIED Requirements

### Requirement: Publish to the device showroom folder
Publishing a batch SHALL move the contents of its `PUBLISH/` directly
into the batch's showroom device folder, as resolved by the library path
mapping. Only the `PUBLISH` component SHALL be stripped.

#### Scenario: Two devices publish the same batch
- **WHEN** Camera and Phone each publish `2026/2026-10 Walk`
- **THEN** files SHALL land in `SHOWROOM/2026/2026-10 Walk/Camera` and
  `SHOWROOM/2026/2026-10 Walk/Phone` respectively
