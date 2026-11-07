# Research: showroom organization and albums

Status: parked for research, not a design. Nothing here is decided until it
becomes an OpenSpec change.

## Intent

Find the good photos and make them reachable by family, durably and without
vendor lock-in. Culling (FastRawViewer) and editing (PhotoLab) work; the
finish line does not, so batches pile up in the darkroom.

Setup: Synology NAS holds showroom and archive; Immich runs on a separate
server and reads the showroom as an external library.

## The problem: one folder name does three jobs

| Concept  | Serves             | Wants to be                                  |
|----------|--------------------|----------------------------------------------|
| Batch    | the photographer   | per device, sized for a sitting, provisional |
| Storage  | backups, Immich    | stable forever once software has seen it     |
| Album    | family             | cross-device, well named, decided late       |

- The old layout (`YEAR/ALBUM/DEVICE`) merged all three from the start: a
  perfect album name was needed before work began, so starting was hard.
- The current layout decouples the batch from early naming, but the showroom
  path is still `YEAR/BATCH/DEVICE`. Showroom folders end up neither albums
  nor a rigid methodology: just clumsy, provisional names.
- Immich treats a moved or renamed file in an external library as a new
  asset. A showroom path is an identifier, not a label: renaming it later
  loses what Immich knows about the photo.

## Approaches considered

1. **Album chosen at publish.** Publish asks for a showroom album folder;
   several batches and devices can publish into it. Small change, folders
   stay the albums, but the name is final once Immich scans it.
2. **Showroom staging.** Publish lands in an area Immich does not scan;
   albums are merged and renamed there, then sealed into the library once.
   Keeps folders as the truth; adds a stage where work can pile up again.
3. **Rigid storage, albums as text.** The showroom never moves; albums are
   plain-text manifests on the NAS, synced to Immich by the tool.
4. **Rigid storage, albums in Immich, exported as text.** Same storage as 3;
   albums are curated in Immich and the tool exports them to text so they
   survive Immich. Optionally a regenerated hardlink folder view outside the
   Immich library gives folder-visible albums.

## Where the discussion landed

- Long term, approach 4 is the preferred direction, not yet committed to.
- Showroom: a rigid, decision-free layout by date and device, like a backup,
  e.g. `showroom/YEAR/YYYY-MM/DEVICE/` (order and precision not settled).
- Archive keeps batches (`archive/YEAR/BATCH/DEVICE/`): several batches in
  one month must not be merged together.
- Albums should ideally be visible as folders; plain text is acceptable.

## Near-term proposal: batch metadata and album at first publish

A smaller step in the spirit of approach 1, proposed separately:

- Creating a batch also creates `batch.yaml` in it, with `album: null`.
- `album`, once set, is the album folder relative to the showroom root, e.g.
  `2026/Grandma's 80th`.
- First publish requires an album: a picker lists showroom album folders
  newest first, or takes a custom name (created as a new folder). The choice
  is saved to `batch.yaml`.
- Later publishes reuse the saved album; if its folder is gone, the picker
  is shown again.
- The batch folder name stays independent and can be renamed freely.

`batch.yaml` is useful in either direction: under approach 4 the same field
could seed a draft Immich album.

## Open questions

- Is folder-as-album the destination, or a bridge towards approach 4?
- Album content: device subfolders (`Camera/`, `Phone/`) or flat files?
  Flat files risk name collisions across devices.
- Album folders are permanent once Immich scans them; how does the picker
  make that clear, and what does a missing album folder mean in practice?
- Existing batches: a missing or unreadable `batch.yaml` should read as
  `album: null`, never as a scan error.
- Scan, tidy and stats must ignore `batch.yaml` so it is not a loose file.
- Archiving a subfolder leaves `batch.yaml` in the darkroom; archiving the
  batch carries it along. Is that the wanted record?
- Reserve the file's shape for later data (publish history, lifecycle
  stage, a stable ID) so it needs no migration.
- Rigid showroom: date precision (month or day), level order, and filename
  collisions when batches of one device and month share a folder (skip
  identical files, block different ones?).
- Existing showroom content: migrate once before investing in Immich albums,
  or freeze it as a legacy import path?
- Where it lands: core concepts (`batch.yaml` in the library index, album
  listing as a query, publish prepare asking for an album) on
  `dev-core-split`, likely after Phase 3 jobs; a GUI-only version on `dev`
  only if relief is urgent.
