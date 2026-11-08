# Spec Delta

## Purpose

Defines culling and editing a batch or subfolder: opening it in the
external app the user configured, at once and without changing files.

## ADDED Requirements

### Requirement: Open in the configured app
Cull and edit SHALL start the command configured for them on the node's
folder and SHALL change no files. In the command, `{folder}` SHALL stand
for the folder and `{first_image_in_folder}` for the first image directly
in it, by name.

#### Scenario: Edit a batch
- **WHEN** the edit command is `editor "{folder}"` and a user edits
  `Camera/2026/2026-10 Walk`
- **THEN** `editor` SHALL be started with that batch's folder

#### Scenario: First image
- **WHEN** the cull command uses `{first_image_in_folder}` and the folder
  holds `b.jpg` and `a.jpg`
- **THEN** the command SHALL be started with `a.jpg`

### Requirement: When the app cannot be started
Culling or editing SHALL be refused, naming the reason, when the command
is not configured, is empty, has an unknown placeholder or bad quoting,
or needs a first image and the folder has none directly in it. A command
that cannot be started, or that exits at once with an error, SHALL be
reported as failed.

#### Scenario: No image in the folder
- **WHEN** the cull command uses `{first_image_in_folder}` and the
  folder's images are all in `PHOTOS/`
- **THEN** culling SHALL be refused, saying no image was found

#### Scenario: App exits with an error
- **WHEN** the edit command exits with an error right after starting
- **THEN** editing SHALL be reported as failed with its exit code
