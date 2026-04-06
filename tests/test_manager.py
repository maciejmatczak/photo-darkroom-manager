"""Tests for DarkroomManager and module helpers."""

from pathlib import Path

import pytest

from photo_darkroom_manager.actions import (
    ArchiveAction,
    NewAlbumAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.manager import (
    DarkroomManager,
    _require_one,
    _translate_path,
)
from photo_darkroom_manager.scan import DarkroomNode
from photo_darkroom_manager.settings import Settings


def _three_roots(tmp_path: Path) -> Settings:
    root = tmp_path / "workspace"
    darkroom = root / "darkroom"
    showroom = root / "showroom"
    archive = root / "archive"
    darkroom.mkdir(parents=True)
    showroom.mkdir()
    archive.mkdir()
    return Settings(darkroom=darkroom, showroom=showroom, archive=archive)


def test_require_one_accepts_single_path() -> None:
    _require_one(Path("/a"), None)
    _require_one(None, Path("/b"))


def test_require_one_rejects_zero_or_two() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        _require_one(None, None)
    with pytest.raises(ValueError, match="exactly one"):
        _require_one(Path("/a"), Path("/b"))


def test_translate_path_preserves_relative_tail() -> None:
    base = Path("/tmp")
    from_root = base / "from"
    to_root = base / "to"
    p = from_root / "2026" / "album" / "x.jpg"
    assert (
        _translate_path(p, from_root, to_root) == to_root / "2026" / "album" / "x.jpg"
    )


def test_darkroom_path_from_showroom_or_archive(tmp_path: Path) -> None:
    settings = _three_roots(tmp_path)
    mgr = DarkroomManager(settings)
    rel = Path("2026") / "album"
    s = settings.showroom / rel
    a = settings.archive / rel
    assert mgr.darkroom_path(showroom_path=s) == settings.darkroom / rel
    assert mgr.darkroom_path(archive_path=a) == settings.darkroom / rel


def test_showroom_path_from_darkroom_or_archive(tmp_path: Path) -> None:
    settings = _three_roots(tmp_path)
    mgr = DarkroomManager(settings)
    rel = Path("2026") / "album"
    d = settings.darkroom / rel
    a = settings.archive / rel
    assert mgr.showroom_path(darkroom_path=d) == settings.showroom / rel
    assert mgr.showroom_path(archive_path=a) == settings.showroom / rel


def test_archive_path_from_darkroom_or_showroom(tmp_path: Path) -> None:
    settings = _three_roots(tmp_path)
    mgr = DarkroomManager(settings)
    rel = Path("2026") / "album"
    d = settings.darkroom / rel
    s = settings.showroom / rel
    assert mgr.archive_path(darkroom_path=d) == settings.archive / rel
    assert mgr.archive_path(showroom_path=s) == settings.archive / rel


def test_path_helpers_reject_zero_or_two_kwargs(tmp_path: Path) -> None:
    settings = _three_roots(tmp_path)
    mgr = DarkroomManager(settings)
    p = settings.darkroom / "2026" / "a"
    with pytest.raises(ValueError, match="exactly one"):
        mgr.darkroom_path()
    with pytest.raises(ValueError, match="exactly one"):
        mgr.darkroom_path(
            archive_path=settings.archive / "x",
            showroom_path=settings.showroom / "x",
        )
    with pytest.raises(ValueError, match="exactly one"):
        mgr.showroom_path()
    with pytest.raises(ValueError, match="exactly one"):
        mgr.showroom_path(darkroom_path=p, archive_path=p)
    with pytest.raises(ValueError, match="exactly one"):
        mgr.archive_path()
    with pytest.raises(ValueError, match="exactly one"):
        mgr.archive_path(darkroom_path=p, showroom_path=p)


def test_rescan_sets_tree_and_scanning_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _three_roots(tmp_path)
    mgr = DarkroomManager(settings)

    fake_node = DarkroomNode(
        path=settings.darkroom,
        name="darkroom",
        node_type="root",
    )

    def scan_and_assert_scanning(p: Path) -> DarkroomNode:
        assert mgr.scanning is True
        assert p == settings.darkroom
        return fake_node

    monkeypatch.setattr(
        "photo_darkroom_manager.manager.scan_darkroom",
        scan_and_assert_scanning,
    )

    assert mgr.scanning is False
    out = mgr.rescan()
    assert out is fake_node
    assert mgr.tree is fake_node
    assert mgr.scanning is False


def test_factory_methods_return_actions_with_expected_paths(tmp_path: Path) -> None:
    settings = _three_roots(tmp_path)
    mgr = DarkroomManager(settings)
    folder = settings.darkroom / "2026" / "album"
    album = folder

    t = mgr.tidy_action(folder)
    assert isinstance(t, TidyAction)
    assert t._folder_path == folder

    ar = mgr.archive_action(folder)
    assert isinstance(ar, ArchiveAction)
    assert ar._folder_path == folder
    assert ar._darkroom_path == settings.darkroom
    assert ar._archive_path == settings.archive

    pub = mgr.publish_action(album)
    assert isinstance(pub, PublishAction)
    assert pub._album_path == album
    assert pub._showroom_path == settings.showroom
    assert pub._darkroom_path == settings.darkroom

    ren = mgr.rename_action(album, "2026-03 new name")
    assert isinstance(ren, RenameAction)
    assert ren._album_path == album
    assert ren._new_name == "2026-03 new name"
    assert ren._darkroom_path == settings.darkroom

    na = mgr.new_album_action("2026", "09", None, "Title")
    assert isinstance(na, NewAlbumAction)
    assert na._darkroom_path == settings.darkroom
    assert na._year == "2026"
    assert na._month == "09"
    assert na._day is None
    assert na._name == "Title"
