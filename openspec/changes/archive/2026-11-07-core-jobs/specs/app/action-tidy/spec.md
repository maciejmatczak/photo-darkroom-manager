# Spec Delta

## Purpose

Defines tidying a batch or subfolder: moving misplaced photos into
`PHOTOS/` and videos into `VIDEOS/` next to them, and what happens when a
file of the same name is already there.

## ADDED Requirements

### Requirement: Tidy moves misplaced media
Tidying a folder SHALL move every photo that is not in a `PHOTOS` folder
into `PHOTOS/` in its own folder, and every video that is not in a
`VIDEOS` folder into `VIDEOS/`, through the whole subtree except
`PUBLISH/`. A photo in `VIDEOS/` or a video in `PHOTOS/` SHALL move to the
sibling folder. Other files SHALL stay where they are.

#### Scenario: Loose files in a batch
- **WHEN** a batch holds `a.jpg`, `b.mp4` and `notes.txt`
- **THEN** after tidying, `a.jpg` SHALL be in `PHOTOS/`, `b.mp4` in
  `VIDEOS/` and `notes.txt` where it was

#### Scenario: Video in the photos folder
- **WHEN** `PHOTOS/` holds `clip.mov`
- **THEN** after tidying, `clip.mov` SHALL be in the sibling `VIDEOS/`

### Requirement: Tidy conflicts
A misplaced file whose target already holds a file of that name, or
whose target another misplaced file also needs, SHALL be a conflict. The
preview SHALL count and list the conflicts. Tidying with conflicts SHALL
be refused unless the user chooses to skip them; skipped files SHALL stay
where they are and the folder SHALL stay untidy.

#### Scenario: Same name already in PHOTOS
- **WHEN** a batch holds a loose `a.jpg` and `b.jpg` and `PHOTOS/` already
  holds an `a.jpg`
- **THEN** the preview SHALL show one file to move and one conflict
- **AND** tidying with skip SHALL move `b.jpg` and leave the loose `a.jpg`

#### Scenario: Refused by default
- **WHEN** the user tidies that batch without choosing to skip
- **THEN** the tidy SHALL be refused, listing the conflict
- **AND** no file SHALL move
