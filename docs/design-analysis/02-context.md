# Phase 2: System context

## Rule for tags

A tag stands for a **role**: what we read from it, what we change in it and
what it promises us. The technology behind it does not count. The same role
gets one tag even when the programs differ; different roles get separate
tags even when the technology is the same. How we talk to a system (a
template, an OS call, a filesystem) is a design question for later phases.

## Tags

| Tag | Read | Change | Promise or concern |
|---|---|---|---|
| `[user]` | Commands, choices, stop requests | Nothing; we show state, previews, progress, results | Always present, whatever the client |
| `[config]` | Settings | Stored when the user changes them | The only thing the app owns |
| `[darkroom]` | Everything: tree, files, counts | Create, rename, move within and out | Work in progress; shared with other tools |
| `[showroom]` | Whether targets exist; later, published batches | Add files; replace only when the user chooses | Immich reads it; files must be complete |
| `[archive]` | Whether targets exist; what blocks a merge | Add files only, never replace | Backed up; it only grows |
| `[external app]` | Nothing back | Start a program on a folder | Cull app, edit app, file manager |
| `[log]` | Nothing today | A record of each run that moves files | Must survive a crash mid-run |

## Decisions

- **Darkroom, showroom and archive are three tags** although they share one
  technology. Their roles, layouts and promises differ, and the walkthroughs
  must show which steps need which area's knowledge. "Three areas over one
  filesystem" is a design decision for Phases 5 and 7.
- **Cull app, edit app and file manager are one tag.** Their role is the
  same: start a program on a folder, read nothing back. The configured apps
  need a user-defined command template and the file manager does not; that
  difference is knowledge, recorded in [knowledge.md](knowledge.md), not a
  different role. A tag would split only if the role changed, for example if
  the app read picks back from the cull app.
- **Reading and changing are balanced.** We read and index almost every file
  in the darkroom and move exactly those files.
- **Concurrent changes are not tracked.** Others (the user in Explorer,
  Synology Drive) may change the disk. Re-checks before acting are for
  confidence; tracking every file move atomically is out of scope.

## Parties we never talk to but must respect

| Party | Why it matters |
|---|---|
| Immich (reads the showroom) | Files appear complete or not at all |
| Synology backups (showroom, archive) | Only complete, correctly placed files land there |
| Synology Drive, the user in Explorer | They change the darkroom whenever they like |
