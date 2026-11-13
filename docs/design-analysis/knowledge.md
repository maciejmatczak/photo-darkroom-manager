# Knowledge inventory (Phase 4, collected while walking through)

One line per decision or piece of knowledge, before naming any modules.
"Seen in" lists the walkthroughs that need it; more than one means a strong
candidate for a single owner.

| Knowledge | Seen in |
|---|---|
| Required settings (the three areas) vs optional ones (cull and edit commands) | Set up |
| Areas must be disjoint: none inside another, none the same folder | Set up |
| How a user-configured command template is rendered for a folder (Jinja-like tokens: folder path, first image), and when it counts as broken | Set up (warn), cull and edit (refuse) |
| A feature backed by an optional setting is disabled until the setting is configured, for every client | Set up, cull, edit |
| First image of a folder: a best guess, directly in the folder, then in its `PHOTOS` | Cull, edit |
| What depends on the darkroom setting, and goes stale when it changes | Set up, see |
| Which devices exist; today the darkroom's top folders, later possibly the config | Set up, new batch |
| Recognising folders: what a folder is from its position and its name together; special names count only directly under a batch; anything else is unrecognised | See, new batch, rename, publish, archive |
| The batch name format: built from a date and a title, read back by recognition and by rename; one owner for both directions | New batch, see, rename |
| Names within one parent are unique regardless of letter case | New batch, rename |
| Every new batch gets a `PUBLISH` folder | New batch |
| The tidy recipe: what is untidy and where each file belongs; one recipe for the status and the run; tweaked often | See, tidy |
| Classifying a file as photo, video or other | See, tidy, cull and edit (first image) |
| A long run shows progress, stops only between files, and records every file | Tidy, publish, archive |
| Clash choices in the user's words: stop if anything clashes, or skip the clashing files; publish may also replace, archive never | Tidy, publish, archive |
| A file never appears half-written in any area the app writes into | Publish, archive |
| How files are moved safely, across drives too; candidate: rclone as a subprocess | Tidy, publish, archive |
| Where a darkroom folder lands in the archive: the batch at `YEAR/BATCH/DEVICE`, everything below keeps its folders; merges into what exists | Archive |
| Removing folders an archive emptied; cleanup that may fail without anything being wrong | Archive |
| Pre-checks before a run (e.g. unpublished files before archive); none today, easy to add | Archive |
| Where a batch lands in the showroom; today from device, year and batch, later through a batch-to-album mapping | Publish |
| What is publishable: the files directly in `PUBLISH`; subfolders there are a warning | Publish |
| What each folder kind allows; fixed per kind, easy to extend | See, and every use case that changes something |
| How counts and attention marks add up the tree | See |
| Every folder the app creates has a safe name | New batch |
| A batch sits in the year folder of its date | New batch, rename |
| Unrecognised folders are shown but not walked into | See |
| A batch's name is shared across areas; renaming may later need to follow in the showroom and archive | Rename, publish, archive |
