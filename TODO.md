# TODO

- [ ] add type checker (ty vs?...)
- [ ] implement tests
- [ ] add support for opening external applications (e.g. for culling, for editing)
- [ ] add logging
- [ ] `ArchiveAction._prepare` should not create directories (side-effect in prepare step); move `target_dir.parent.mkdir(...)` to `_execute` instead
