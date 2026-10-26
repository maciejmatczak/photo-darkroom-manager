# Device-first batches design

## Intent

Organize active photo work by device. Rename the existing album concept to
batch so its name can be provisional and intake, editing, RAW development,
and publishing can proceed without perfect album organization upfront.

A batch keeps today's album creation rules and actions. This change does
not introduce a new processing workflow or metadata model.

## Agreed layout

```text
DARKROOM/DEVICE/YEAR/BATCH/
  PUBLISH/
  loose files and optional subfolders
  PHOTOS/    (created by Tidy when needed)
  VIDEOS/    (created by Tidy when needed)

ARCHIVE/YEAR/BATCH/DEVICE/
  archived files and subfolders

SHOWROOM/YEAR/BATCH/DEVICE/
  published files
```

Batch names retain `YYYY-MM[-DD][ title]`, including existing validation,
defaults, and optional day/title. No diacritics change is included here.

Publishing moves the contents of a batch's `PUBLISH` directory directly
into its showroom device directory. Archiving preserves the selected
subtree below the device's batch. Two devices with identical year/batch
names share a destination batch parent but retain separate device folders.

## UI and creation

- The tree remains derived exclusively from darkroom. Fully archived
  batches disappear after refresh, as today.
- Device and year nodes provide Open in Explorer, counts, issues, and
  expand/collapse only. There is no New Batch action on device rows.
- Batch nodes inherit all current album actions. Subfolders and `PUBLISH`
  keep their existing action behavior.
- The toolbar uses New Batch. Its form offers existing device folder names
  plus custom name entry. No device registry is introduced.
- Creation makes missing device/year parents, the batch, and `PUBLISH`.
  Loose media may sit beside `PUBLISH`; Tidy handles it as today.
- Archive and showroom Open buttons use the reordered destination paths
  and retain existing directory-existence enablement.
- Application terminology changes from Album to Batch throughout.

## Approaches and decision

The discussion considered matching device-first layouts in all roots.
The user selected device-first darkroom with year/batch/device ordering in
archive and showroom. This keeps active work grouped by device while
grouping stored results by year and batch. It requires explicit reversible
path mapping instead of root substitution.

A combined catalog spanning all roots was discussed after discovering
that archive-only batches do not appear today. The user explicitly chose
to retain the darkroom-based UI. Unarchive is not an existing action and
is not being added. Reverse path helpers remain supported.

## Constraints and implementation defaults

- Code, documentation, and test fixtures only. The user migrates real
  photo folders manually; no migration command or real-data operation.
- No legacy darkroom layout support in the completed change.
- Keep configured roots, settings format, external-tool configuration,
  move semantics, and conflict handling unchanged.
- Rename changes only the darkroom folder. Names remain path-based
  anchors; no coordinated rename or persistent identity is added.
- Preserve the existing subfolder-to-showroom link behavior, even when a
  corresponding published subfolder does not exist.
- Keep Python 3.13 and the existing NiceGUI/Pydantic stack; no dependencies.
- Wrap all generated markdown files at 80 columns.
- Implementation default: refresh device choices when opening the form,
  sort by name, include empty directories, and require explicit selection.
- Implementation default: custom names must be safe single directory
  components on Windows; allow spaces and Unicode, reject reserved media
  directory names. Details are pinned in the implementation plan.

No progress tracking, device profiles, photo preview, new transfer engine,
or archive/showroom scanning is part of this change.
