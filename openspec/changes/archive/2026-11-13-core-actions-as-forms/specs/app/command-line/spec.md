# Spec Delta

## MODIFIED Requirements

### Requirement: Preview by default
Without `--apply` or `--confirm`, a command for a planned action SHALL
print what that action will do, in its own terms, what the user must
decide, the fingerprint and the command that confirms it, and change
nothing. A command for a direct action SHALL
run at once.

#### Scenario: Archive preview
- **WHEN** a user runs `darkroom archive .` inside a batch
- **THEN** where the batch goes and how many files move, `plan` with the
  fingerprint, and the `--confirm` command SHALL be printed
- **AND** no file SHALL be moved

#### Scenario: Open runs at once
- **WHEN** a user runs `darkroom open .`
- **THEN** the folder SHALL open without `--apply` or `--confirm`

#### Scenario: Preview with conflicts
- **WHEN** a user previews archive of a batch with 10 files already in
  the archive
- **THEN** the preview SHALL say that 10 files are already in the archive
- **AND** the printed `--confirm` command SHALL carry the conflict option
  the user gave, if any
