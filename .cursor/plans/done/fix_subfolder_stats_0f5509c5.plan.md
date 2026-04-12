---
name: Fix subfolder stats
overview: Subfolder and album nodes do not self-aggregate their stats. Fix by adding `node.stats = _aggregate_stats(node)` inside both `_scan_subfolder` and `_scan_album`, then removing the now-redundant call from `_scan_year`.
todos:
  - id: fix-scan-subfolder
    content: Add `node.stats = _aggregate_stats(node)` before `return node` in `_scan_subfolder`
    status: completed
  - id: fix-scan-album
    content: Add `node.stats = _aggregate_stats(node)` before `return node` in `_scan_album`, and remove the redundant `album_node.stats = _aggregate_stats(album_node)` line from `_scan_year`
    status: completed
isProject: false
---

# Fix Subfolder Accumulated Stats

## Root Cause

In [`src/photo_darkroom_manager/scan.py`](src/photo_darkroom_manager/scan.py), neither `_scan_subfolder` nor `_scan_album` aggregate their stats before returning. The album aggregation currently happens in the **caller** (`_scan_year`, line 142), which is inconsistent and easy to miss or break. `_scan_subfolder` has no aggregation at all, causing the bug.

The correct pattern — already followed by `_scan_year` and `scan_darkroom` — is for each function to aggregate its own node before returning.

## Fix

**`_scan_subfolder`** — add aggregation before `return`:

```python
    node.stats = _aggregate_stats(node)
    return node
```

**`_scan_album`** — same addition:

```python
    node.stats = _aggregate_stats(node)
    return node
```

**`_scan_year`** — remove the now-redundant caller-side aggregation of album nodes (line 142):

```python
# Before
album_node = _scan_album(child_dir)
album_node.stats = _aggregate_stats(album_node)  # ← remove this
node.children.append(album_node)

# After
album_node = _scan_album(child_dir)
node.children.append(album_node)
```

No changes needed in `layout.py` — the GUI already reads `node.stats` correctly.
