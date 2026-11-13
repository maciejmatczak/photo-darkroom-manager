# Phase 4: Knowledge inventory

One line per decision or piece of knowledge, before naming any modules.
Each line should be able to change independently of the others. "Seen in"
lists the walkthroughs that need it; more than one means a strong candidate
for a single owner.

Kinds: **format** (how something is written and read back), **rule** (what
is true or allowed), **policy** (a choice that could reasonably be
different), **sequence** (steps in an order).

## Settings

| Knowledge | Kind | Seen in |
|---|---|---|
| Required settings (the three areas) vs optional ones (cull and edit commands) | Rule | Set up |
| Areas never overlap: none inside another, none the same folder | Rule | Set up |
| A feature backed by an optional setting is disabled until the setting is configured, for every client | Rule | Set up, cull, edit |
| What depends on the darkroom setting, and goes stale when it changes | Rule | Set up, see |

## Darkroom layout and names

| Knowledge | Kind | Seen in |
|---|---|---|
| Recognising folders: what a folder is from its position and its name together; special names count only directly under a batch; anything else is unrecognised | Rule | See, new batch, rename, publish, archive |
| Unrecognised folders are shown but not walked into | Policy | See |
| Which devices exist; today the darkroom's top folders, later possibly the config | Rule | Set up, new batch |
| The batch name: built from a date and a title, read back by recognition and by rename; one owner for both directions | Format | New batch, see, rename |
| A batch sits in the year folder of its date | Rule | New batch, rename |
| Every new batch gets a `PUBLISH` folder | Rule | New batch |
| Every folder the app creates has a safe name | Rule | New batch |
| Names within one parent are unique regardless of letter case; for folders and files | Rule | New batch, rename, tidy, publish, archive |
| A batch's name is shared across areas; renaming may later need to follow in the showroom and archive | Rule | Rename, publish, archive |

## The darkroom view

| Knowledge | Kind | Seen in |
|---|---|---|
| What each folder kind allows; fixed per kind, easy to extend | Rule | See, and every use case that changes something |
| How counts and attention marks add up the tree | Rule | See |
| Which part of the darkroom view each change makes stale (the folder, the batch, the parent, the old and new year) | Rule | New batch, rename, tidy, publish, archive |

## Files and tidiness

| Knowledge | Kind | Seen in |
|---|---|---|
| Classifying a file as photo, video or other | Rule | See, tidy, cull and edit (first image) |
| The tidy recipe: what is untidy and where each file belongs; one recipe for the status and the run; tweaked often | Policy | See, tidy |

## Places in other areas

| Knowledge | Kind | Seen in |
|---|---|---|
| Where a batch lands in the showroom: today `YEAR/BATCH/DEVICE`, later through a batch-to-album mapping | Rule | Publish |
| What is publishable: the files directly in `PUBLISH`; subfolders there are a warning | Policy | Publish |
| Where a darkroom folder lands in the archive: the batch at `YEAR/BATCH/DEVICE`, everything below keeps its folders; merges into what exists | Rule | Archive |

## Running changes

| Knowledge | Kind | Seen in |
|---|---|---|
| Which use cases show what will happen and wait for the user; easy to add or drop per use case | Policy | New batch (open), rename, tidy, publish, archive |
| Pre-checks before a run (e.g. unpublished files before archive); none today, easy to add | Policy | Archive |
| Clash choices in the user's words: stop if anything clashes, or skip the clashing files; publish may also replace, archive never | Policy | Tidy, publish, archive |
| Each target is re-checked just before its file moves | Rule | Tidy, publish, archive |
| How files are moved safely, across drives too | Sequence | Tidy, publish, archive |
| A file never appears half-written in any area the app writes into | Rule | Publish, archive |
| A long run can be watched and stopped between files | Sequence | Tidy, publish, archive |
| Every file a run touches is recorded | Rule | Tidy, publish, archive |
| What a run reports: moved, skipped, replaced, failed, not reached, left behind | Format | Tidy, publish, archive |
| Removing folders an archive emptied; cleanup that may fail without anything being wrong | Policy | Archive |

## External apps

| Knowledge | Kind | Seen in |
|---|---|---|
| The command template: Jinja-like tokens (folder path, first image), how it is rendered for a folder, and when it counts as broken | Format | Set up (warn), cull and edit (refuse) |
| First image of a folder: a best guess, directly in the folder, then in its `PHOTOS` | Policy | Cull, edit |
