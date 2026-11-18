# Phase 3: Use-case walkthroughs

One walkthrough per use case, each step tagged with the system it touches
(see [02-context.md](02-context.md)). Steps hold for any client.

## 1. Set up (startup included)

1. Read the settings. `[config]`
2. If there are none, tell the user the app is not set up yet. `[user]`
3. Check that each area's folder exists and is a folder. `[darkroom]`
   `[showroom]` `[archive]`
4. Check that no area lies inside another or is the same folder as another.
   If one does, the app is not ready.
5. Check that each optional command that is set can be rendered. A broken
   one gives a warning; the app is still ready.
6. Load the existing devices; today, the darkroom's top folders.
   `[darkroom]`
7. Show the state: ready or not, what is wrong with the required settings,
   warnings for the optional ones. `[user]`
8. The user changes a setting; the app checks the value. `[user]`
9. Store the changed settings. `[config]`
10. If the darkroom changed, nothing learned about the old darkroom applies
    any more.

Decided:

- Overlapping areas are a critical problem: the app refuses them.
- The three areas are required. The cull and edit commands are optional
  extras; the app works without them. A command that cannot be rendered is
  a warning at set up and a refusal when used.
- "Stored" states the guarantee, not the mechanism (save button or save on
  change).
- Whether a value is a lasting setting or a runtime value seeded from one
  (like the log level) depends on the client's lifetime. Parked for design.

## 2. See the darkroom

1. The app must be set up; it needs the darkroom folder. `[config]`
2. Walk the darkroom's folders. `[darkroom]`
3. Decide what each folder is: device, year, batch, `PUBLISH`, a bucket, a
   subfolder, or unrecognised when it breaks the layout.
4. Count the photos, videos and other files in each folder, by extension.
   `[darkroom]`
5. Mark folders that need attention: untidy.
6. Add the counts and attention marks up the tree.
7. Show the tree. What can be done on each folder depends on its kind only.
   `[user]`
8. The user can ask about one folder only; the app reads just that folder
   and the path to it. `[darkroom]`

Decided:

- What can be done depends on the folder's kind, not its state. A stateful
  rule (for example "nothing to publish") would need watching the disk.
- A folder that breaks the layout is shown as an unrecognised folder, so the
  user sees that something is off and can fix it. The app does not walk
  into it. It has a small set of its own: at least open. The set must be
  easy to extend later.
- An unrecognised folder shows no counts for now. Changing that must be
  simple.

## 3. New batch

1. The user picks a device, either an existing one or a new name. `[user]`
2. The user gives a date (year and month, optionally a day) and optionally a
   title. `[user]`
3. Check that a new device name is a safe folder name.
4. Build the batch name from the date and title.
5. Work out where it goes: `DEVICE/YEAR/BATCH`, with `PUBLISH` inside.
6. Refuse if the batch name clashes with an existing one under the same
   year, ignoring letter case, or if a file sits where the device or year
   folder must be. `[darkroom]`
7. Show where the batch will be, and warn when a new device would be
   created; wait for the user. It must be cheap to change either way
   *(decided in Phase 7h)*. `[user]`
8. Create the missing folders. `[darkroom]`
9. The darkroom view now shows the new batch.

Decided:

- Every folder the app creates has a safe name.
- A device may have any safe name, `Photos` included. Special folder names
  count only directly under a batch.
- Names within one parent are unique regardless of letter case; a name that
  differs from an existing one only in case is a clash.

## 4. Rename

Before: the darkroom is shown (walkthrough 2), so the batch, its date and
its title are already known.

1. The user picks a batch and gives a new date, a new title, or asks to drop
   the title; what is not given stays as it is. `[user]`
2. Build the new name from the date and title.
3. If the name does not change, say so and stop. `[user]`
4. Work out where the batch goes: the year folder of its date.
5. Refuse if the name clashes with another folder there, ignoring letter
   case. Changing only the case of this batch's own name is allowed.
   `[darkroom]`
6. Show the change and wait for the user. Keep it easy to drop. `[user]`
7. Rename the batch; if its year changed, move it to that year folder,
   creating the folder if needed. `[darkroom]`
8. The darkroom view shows the batch under its new name and place.
   Anything that referred to it now refers to the new one. `[user]`

Decided:

- A batch always sits in the year folder of its date. A new date in another
  year moves the batch there.
- Rename never meets an unreadable batch name: such a folder is unrecognised
  (walkthrough 2) and is not offered rename.
- Today rename changes only the darkroom. Keeping the showroom and archive
  in step is likely later; it must be easy to add.
- A year folder emptied by the move is left in place for now. Removing it
  later must not have a large impact.

## 5. Tidy

Before: the darkroom is shown. Each folder shows whether it is tidy; a
folder is untidy when it or any folder below it holds a photo or video
outside its bucket.

1. The user sees a folder marked untidy: a batch, a subfolder, or possibly
   another kind. `[user]`
2. The user asks to tidy it. `[user]`
3. Find every photo and video outside its bucket, in this folder and the
   folders below it. `[darkroom]`
4. Classify each file: photos belong in `PHOTOS`, videos in `VIDEOS`, beside
   where they are now.
5. Find clashes: the target is already taken (ignoring letter case), or two
   files want the same target. `[darkroom]`
6. Show what will move and the clashes. The user confirms and chooses to
   stop if anything clashes, or to skip the clashing files. `[user]`
7. Move the files one by one. The user sees progress, can stop between
   files, and every file is recorded. `[darkroom]` `[log]`
8. Report what moved, was skipped, failed or was not reached. `[user]`
9. The folder's tidy status is updated. `[user]`

Decided:

- **One tidy recipe** decides what is untidy and where each file belongs.
  The tidy status and the tidy run both use it, so they can never disagree.
- The recipe will be tweaked often; changing it must not require changing
  the rest of the software.
- Starting recipe, good enough for now:
  - photos belong in `PHOTOS`, videos in `VIDEOS`; a video in `PHOTOS`
    moves to the sibling `VIDEOS`, and the other way round;
  - files anywhere inside a bucket, its subfolders included, are tidy;
  - `PUBLISH` is not tidied: exports stay flat for publish;
  - unrecognised folders are not looked into, as in see.
- Clean what the recipe knows how to clean. Files it cannot place are
  left alone and shown to the user, not counted as tidy *(Phase 7)*.
- Known gaps in the recipe, to tweak later:
  - a video inside a subfolder of `PHOTOS` (or a photo inside one of
    `VIDEOS`) is left alone and shown; how to move it without flattening
    its folders is unclear;
  - whether files in a batch's subfolder belong in that subfolder's buckets
    or in the batch's own buckets.

## 6 and 7. Cull and edit

The same steps; cull reads the cull command, edit the edit command.

Before: the darkroom is shown; the folder is a batch or a subfolder; the
command is configured.

1. The user picks a folder and asks to cull it. `[user]`
2. Render the command for this folder from its template. Tokens include the
   folder's path and the first image in the folder. `[config]` `[darkroom]`
3. If it cannot be rendered (an unknown token, no image found), say why and
   stop. `[user]`
4. Start the cull app. `[external app]`
5. If it fails to start or exits with an error straight away, say so.
   `[user]`

Decided:

- An unconfigured command means the feature is disabled, for every client.
  Every client can tell it is disabled; only a configured command enables
  it.
- The command is a template in the spirit of Jinja, with tokens such as the
  folder's path and the first image in the folder.
- No preview and no confirm: nothing in the darkroom changes.
- "First image" is a best guess, not a layout rule: look directly in the
  folder, then in its `PHOTOS`. If none is found, say so honestly. It is
  independent of the tidy recipe; photos may sit anywhere at any moment.

## 8. Open

Before: the darkroom is shown.

1. The user picks any folder, unrecognised ones included, and asks to open
   it. `[user]`
2. Show it in the file manager. `[external app]`
3. If that fails, say so. `[user]`

Decided:

- Open is available on every folder kind and needs no settings.

## 9. Publish

Before: the darkroom is shown; the folder is a batch.

1. The user picks a batch and asks to publish it. `[user]`
2. List the files directly in its `PUBLISH`. If it holds subfolders, warn
   and carry on with the files. If there are no files, say there is
   nothing to publish and stop. `[darkroom]`
3. Work out the batch's place in the showroom: `YEAR/BATCH/DEVICE`.
4. Find clashes: a file of the same name already there, ignoring letter
   case. `[showroom]`
5. Show what will move, the warning and the clashes. The user confirms and
   chooses: stop if anything clashes, skip the clashing files, or replace
   them. `[user]`
6. Move the files one by one. A file never appears in the showroom
   half-written. The user sees progress, can stop between files, and every
   file is recorded. `[darkroom]` `[showroom]` `[log]`
7. Report what moved, was skipped, was replaced, failed or was not
   reached. `[user]`
8. The darkroom view is updated for the batch.

Decided:

- Subfolders in `PUBLISH` are a warning, not a refusal: the files directly
  in it are still published and the subfolders are left alone.
- Replace is allowed when the user chooses it; the replaced showroom file
  is gone. Recovering it is the showroom's backup policy, outside this app.
- Where a batch lands in the showroom will change: later a batch maps to an
  album that lives and is managed on the showroom side (picked or curated,
  like a batch). Not today, but the place must have one owner so that this
  change stays small.
- The showroom keeps a device folder under each batch (`YEAR/BATCH/DEVICE`),
  so devices publishing the same batch never clash.

## 10. Archive

Before: the darkroom is shown; the folder is a batch or a subfolder.

1. The user picks a batch or a subfolder and asks to archive it. `[user]`
2. List every file in it and below it, whatever the folders are.
   `[darkroom]`
3. Work out each file's place in the archive: the batch goes to
   `YEAR/BATCH/DEVICE` and everything below keeps its folders. Archiving
   merges into whatever is already there.
4. Find clashes (a file of the same name at the target, ignoring letter
   case) and blockers (a file where a folder must go). `[archive]`
5. Show what will move and the clashes. The user confirms and chooses: stop
   if anything clashes, or skip the clashing files. Never replace. `[user]`
6. Move the files one by one. A file never appears in the archive
   half-written. The user sees progress, can stop between files, and every
   file is recorded. `[darkroom]` `[archive]` `[log]`
7. Remove the folders that are now empty; a folder held open elsewhere
   stays. `[darkroom]`
8. Report what moved, was skipped, failed or was not reached, and what is
   still left in the darkroom. `[user]`
9. The darkroom view is updated from the parent folder down.

Decided:

- Archive works on paths and asks no questions about what the folders are:
  unrecognised folders and `PUBLISH` go along with everything else.
- Unpublished files in `PUBLISH` are not checked for now. The construction
  must make adding such a pre-check easy (a change scenario for Phase 6).
- "Never half-written" holds for the archive too: it is a promise of every
  area the app writes into.
- Heavy file movement may later be handed to rclone as a subprocess, which
  would take the movement itself out of the app while keeping it auditable.
  A design option for Phase 7, not a decision.

- Heavy runs are recorded here as needs only (progress, stop between files,
  record every file). The concept that holds them is decided after the
  knowledge inventory.
