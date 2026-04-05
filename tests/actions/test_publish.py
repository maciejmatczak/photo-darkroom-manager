"""Tests for PublishAction prepare and execute."""

from pathlib import Path

from photo_darkroom_manager.actions import PrepareError, PublishAction, PublishPlan
from photo_darkroom_manager.settings import PUBLISH_FOLDER

PUBLISH_ALBUM_BASIC_REL = Path("2026") / "2026-03 publish basic success"
PUBLISH_ALBUM_OVERWRITE_REL = Path("2026") / "2026-03 publish will overwrite conflicts"
PUBLISH_ALBUM_FAIL_MISSING_REL = (
    Path("2026") / "2026-03 publish will fail missing publish dir"
)
PUBLISH_ALBUM_FAIL_EMPTY_REL = (
    Path("2026") / "2026-03 publish will fail empty publish dir"
)
PUBLISH_ALBUM_FAIL_SUBDIR_REL = (
    Path("2026") / "2026-03 publish will fail publish has subdir"
)


def _file_names_in_publish(publish_dir: Path) -> frozenset[str]:
    return frozenset(p.name for p in publish_dir.iterdir() if p.is_file())


def test_publish_prepare_happy_empty_conflicts(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_BASIC_REL)
    publish_dir = album / PUBLISH_FOLDER
    expected_names = _file_names_in_publish(publish_dir)
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    out = act._prepare()
    assert isinstance(out, PublishPlan)
    assert out.conflict_pairs == ()
    assert frozenset(f.name for f in out.files) == expected_names
    expected_target = (
        photo_setup.settings.showroom / PUBLISH_ALBUM_BASIC_REL
    ).resolve()
    assert out.target_dir == expected_target


def test_publish_prepare_conflict_pairs_when_showroom_has_same_name(
    photo_setup,
) -> None:
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_OVERWRITE_REL)
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    out = act._prepare()
    assert isinstance(out, PublishPlan)
    assert len(out.conflict_pairs) == 1
    src, dst = out.conflict_pairs[0]
    assert src.name == dst.name == "same_name_0001.jpg"
    assert dst.is_file()


def test_publish_prepare_fails_when_publish_dir_missing(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_FAIL_MISSING_REL)
    assert not (album / PUBLISH_FOLDER).exists()
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    out = act._prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "PUBLISH directory does not exist"


def test_publish_prepare_fails_when_publish_dir_empty(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_FAIL_EMPTY_REL)
    publish_dir = album / PUBLISH_FOLDER
    assert publish_dir.is_dir()
    assert _file_names_in_publish(publish_dir) == frozenset()
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    out = act._prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "PUBLISH directory is empty"


def test_publish_prepare_fails_when_publish_has_subdir(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_FAIL_SUBDIR_REL)
    publish_dir = album / PUBLISH_FOLDER
    nested = [p for p in publish_dir.iterdir() if p.is_dir()]
    assert nested
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    out = act._prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "PUBLISH directory contains subdirectories"


def test_publish_execute_moves_files_to_showroom(photo_setup) -> None:
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_BASIC_REL)
    publish_dir = album / PUBLISH_FOLDER
    names = _file_names_in_publish(publish_dir)
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    plan = act._prepare()
    assert isinstance(plan, PublishPlan)
    result = act._execute(plan)
    assert result.success
    assert f"{len(names)} file" in result.message

    showroom_album = photo_setup.settings.showroom / PUBLISH_ALBUM_BASIC_REL
    for name in names:
        assert (showroom_album / name).is_file()
        assert not (publish_dir / name).exists()


def test_publish_execute_unlinks_dest_then_replaces_on_conflict(photo_setup) -> None:
    """Dest existed in showroom; execute unlinks it then moves from PUBLISH."""
    album = photo_setup.darkroom_has_dir(PUBLISH_ALBUM_OVERWRITE_REL)
    publish_dir = album / PUBLISH_FOLDER
    act = PublishAction(
        album,
        photo_setup.settings.showroom,
        photo_setup.settings.darkroom,
    )
    plan = act._prepare()
    assert isinstance(plan, PublishPlan)
    assert len(plan.conflict_pairs) == 1

    result = act._execute(plan)
    assert result.success

    dest = (
        photo_setup.settings.showroom
        / PUBLISH_ALBUM_OVERWRITE_REL
        / "same_name_0001.jpg"
    )
    assert dest.is_file()
    assert not (publish_dir / "same_name_0001.jpg").exists()
