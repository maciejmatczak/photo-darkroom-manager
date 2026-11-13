# Phase 1: Product brief

## Problem

Photos and videos come off a camera and a phone and go through three places:
the darkroom (work in progress), the showroom (finished photos, read by
Immich) and the archive (all source material). Moving files between them by
hand is slow (each place has its own folder layout), risky (a file gets
overwritten, or a move dies halfway over the network and nobody knows what
moved) and opaque (no overview of what is untidy, waiting to publish or left
to archive).

## Users

- The photographer, at a PC, with the showroom and archive on a NAS.
- An AI agent is not a user yet. The CLI is the client and may serve agents
  later; machine-readable output is a nice-to-have.

## Use cases

| # | Use case | User goal |
|---|---|---|
| 1 | Set up | Point the app at the three areas and the external apps |
| 2 | See the darkroom | Know what is there and what needs attention |
| 3 | New batch | Start a batch for a device |
| 4 | Rename | Fix a batch's date or title |
| 5 | Tidy | Put photos and videos into their buckets |
| 6 | Cull | Open a batch in the cull app |
| 7 | Edit | Open a batch in the edit app |
| 8 | Open | See a folder in the file manager |
| 9 | Publish | Send finished files to the showroom |
| 10 | Archive | Send source material to the archive |

Stopping a run and following its progress are part of tidy, publish and
archive, not goals of their own.

Every use case that moves files shows what will happen first, does exactly
that, can be stopped, and reports what moved, what did not and why.

## Assumptions

- One user and one app running at a time.
- One darkroom, one showroom, one archive.
- Files only flow out of the darkroom, never back.
- No undo: safety comes from previews and refusing conflicts.

## Out of scope

- Getting files from drop-off into a batch (done by hand).
- Culling and editing (external apps), cataloguing (Immich), backups
  (Synology).
- Migrating the old album layout.

## On the roadmap, not in scope yet

- **Showroom albums.** A published batch may no longer be in the darkroom
  (archived) but still be in the showroom. When a new device brings files
  for the same event, the showroom album is a useful reference. This needs
  the showroom to be read and indexed, which the app does not do yet.

## Vocabulary

darkroom, showroom, archive, device, batch, publish, tidy, cull, edit,
untidy, `PUBLISH`, `PHOTOS`, `VIDEOS`.
