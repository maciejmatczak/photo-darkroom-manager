"""Contract: app/command-line commands, output, errors and exit codes."""

import io
import json
import sys
import threading
import time
import tomllib
from pathlib import Path

import pytest
import yaml

from cli.conftest import BATCH, Cli, Run
from photo_darkroom_manager.cli import _app as app_module
from photo_darkroom_manager.cli import main, run
from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.actions import _actions as actions_module
from photo_darkroom_manager.core.engine import Engine
from photo_darkroom_manager.core.library import _scan as scan_module

COMMANDS = (
    "status",
    "config",
    "inspect",
    "open",
    "tidy",
    "cull",
    "edit",
    "rename",
    "publish",
    "archive",
    "new-batch",
)
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _ok(out: Run) -> dict:
    assert out.code == 0, out
    return out.json()


def _confirm_argv(preview: Run) -> list[str]:
    """The printed ``--confirm`` command, as argv without the program name."""
    argv = _ok(preview)["result"]["confirm"]
    assert argv[0] == "darkroom"
    return argv[1:]


# ---------------------------------------------------------------------------
# Commands, short name
# ---------------------------------------------------------------------------


def test_help_lists_the_commands(cli: Cli) -> None:
    out = cli("--help")
    assert out.code == 0
    assert out.out.startswith("usage: darkroom")
    for command in COMMANDS:
        assert f"    {command} " in out.out


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_describes_itself(cli: Cli, command: str) -> None:
    out = cli(command, "--help")
    assert out.code == 0
    assert f"usage: darkroom {command}" in out.out.replace("\n", " ")


def test_alias_runs_the_same_command(
    cli: Cli, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts["darkroom"] == scripts["dr"] == "photo_darkroom_manager.cli:main"

    batch = cli.batch("a.jpg")
    monkeypatch.chdir(batch)
    outputs = []
    for prog in ("darkroom", "dr"):
        monkeypatch.setattr(sys, "argv", [prog])
        assert main(["--config", str(cli.config), "inspect", "."]) == 0
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1]
    assert outputs[0].startswith(BATCH)

    monkeypatch.setattr(sys, "argv", ["dr"])
    assert main(["--help"]) == 0
    assert capsys.readouterr().out.startswith("usage: darkroom")


# ---------------------------------------------------------------------------
# status and config
# ---------------------------------------------------------------------------


def test_status_on_an_unconfigured_engine(cli: Cli, tmp_path: Path) -> None:
    missing = tmp_path / "nowhere.yaml"
    out = io.StringIO()
    code = run(
        ["--json", "--config", str(missing), "status"],
        cwd=cli.home,
        stdout=out,
        stderr=io.StringIO(),
    )
    assert code == 0
    result = json.loads(out.getvalue())["result"]
    assert result["status"] == "unconfigured"
    assert [i["key"] for i in result["issues"]] == ["darkroom", "showroom", "archive"]
    assert not missing.exists()


def test_status_ready(cli: Cli) -> None:
    out = cli("status")
    assert out.code == 0
    assert "status: ready" in out.out
    assert f"darkroom: {cli.roots.darkroom}" in out.out


def test_set_the_archive_root(cli: Cli, tmp_path: Path) -> None:
    new_archive = tmp_path / "New Archive"
    new_archive.mkdir()
    out = cli("config", "set", "archive", str(new_archive))
    assert out.code == 0
    stored = yaml.safe_load(cli.config.read_text(encoding="utf-8"))
    assert Path(stored["archive"]) == new_archive.resolve()


def test_set_a_root_relative_to_the_current_folder(cli: Cli) -> None:
    (cli.home / "Archive").mkdir()
    assert cli("config", "set", "archive", "Archive").code == 0
    stored = yaml.safe_load(cli.config.read_text(encoding="utf-8"))
    assert Path(stored["archive"]) == (cli.home / "Archive").resolve()


def test_invalid_log_level(cli: Cli) -> None:
    before = cli.config.read_text(encoding="utf-8")
    out = cli("--json", "config", "set", "log_level", "LOUD")
    assert out.code == 3
    error = out.json()["error"]
    assert error["kind"] == "invalid_value"
    assert "log_level" in error["message"]
    assert cli.config.read_text(encoding="utf-8") == before


def test_config_list_and_get(cli: Cli) -> None:
    listed = _ok(cli("--json", "config", "list"))["result"]
    assert list(listed["values"]) == [
        "darkroom",
        "showroom",
        "archive",
        "cull_command",
        "edit_command",
        "log_level",
    ]
    got = _ok(cli("--json", "config", "get", "log_level"))["result"]
    assert got == {"key": "log_level", "value": "INFO"}
    unknown = cli("config", "get", "colour")
    assert unknown.code == 3
    assert "colour" in unknown.err


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def test_batch_with_depth_one(cli: Cli) -> None:
    batch = cli.batch("a.jpg", "PHOTOS/b.jpg", "PHOTOS/deep/c.jpg")
    result = _ok(cli("--json", "inspect", "--depth", "1", cwd=batch))["result"]
    assert result["id"] == BATCH
    assert result["total"]["images"] == 3
    (photos,) = result["children"]
    assert photos["name"] == "PHOTOS"
    assert photos["child_count"] == 1
    assert "children" not in photos

    text = cli("inspect", "--depth", "1", cwd=batch).out
    assert "PHOTOS  [subfolder]  2 images" in text
    assert "deep" not in text
    assert "… 1 more below" in text


def test_machine_readable_inspect(cli: Cli) -> None:
    cli.batch("a.jpg")
    out = cli("--json", "inspect", "id:Camera")
    assert out.code == 0
    document = json.loads(out.out)
    assert document["format"] == 1
    assert document["command"] == "inspect"
    assert document["ok"] is True
    node = document["result"]
    assert node["id"] == "Camera"
    assert [c["id"] for c in node["children"]] == ["Camera/2026"]


def test_one_batch_in_a_large_library(
    cli: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli.batch("a.jpg")
    cli.batch("b.jpg", node_id="Phone/2026/2026-10 x")
    read: list[Path] = []
    real = scan_module._subfolders

    def spy(directory: Path) -> list[Path]:
        read.append(directory)
        return real(directory)

    monkeypatch.setattr(scan_module, "_subfolders", spy)
    assert cli("inspect", f"id:{BATCH}").code == 0
    phone = cli.roots.darkroom / "Phone"
    assert read
    assert not any(p == phone or phone in p.parents for p in read)


def test_inspect_without_a_target_outside_the_darkroom(cli: Cli) -> None:
    cli.batch()
    result = _ok(cli("--json", "inspect"))["result"]
    assert result["id"] == ""
    assert result["complete"] is True


# ---------------------------------------------------------------------------
# preview, apply, confirm
# ---------------------------------------------------------------------------


def test_archive_preview(cli: Cli) -> None:
    batch = cli.batch("a.jpg", "b.jpg")
    out = cli("archive", ".", cwd=batch)
    assert out.code == 0
    assert "Archive 2 files" in out.out
    assert "move a.jpg → a.jpg" in out.out
    fingerprint = next(
        line.split()[1] for line in out.out.splitlines() if line.startswith("plan ")
    )
    assert f"--confirm {fingerprint}" in out.out
    assert f'archive "id:{BATCH}"' in out.out
    assert (batch / "a.jpg").is_file()
    assert not any(cli.roots.archive.rglob("*.jpg"))


def test_confirm_the_plan_shown(cli: Cli) -> None:
    batch = cli.batch("a.jpg", "b.jpg")
    argv = _confirm_argv(cli("--json", "archive", ".", cwd=batch))
    out = cli(*argv)
    assert out.code == 0, out
    archived = cli.roots.archive / "2026/2026-10 Walk/Camera"
    assert (archived / "a.jpg").is_file()
    assert (archived / "b.jpg").is_file()
    assert out.json()["result"]["node_id"] is None


def test_confirm_a_stale_plan(cli: Cli) -> None:
    batch = cli.batch("a.jpg")
    preview = _ok(cli("--json", "archive", f"id:{BATCH}"))["result"]
    (batch / "late.jpg").write_bytes(b"")
    out = cli("--json", "archive", f"id:{BATCH}", "--confirm", preview["fingerprint"])
    assert out.code == 3
    document = out.json()
    assert document["ok"] is False
    assert document["error"]["kind"] == "refused"
    message = document["error"]["message"]
    current = document["result"]["fingerprint"]
    assert preview["fingerprint"] in message
    assert current in message
    assert current != preview["fingerprint"]
    assert (batch / "a.jpg").is_file()


def test_both_options(cli: Cli) -> None:
    cli.batch("a.jpg")
    out = cli("archive", f"id:{BATCH}", "--apply", "--confirm", "abc")
    assert out.code == 2
    assert "not allowed with argument" in out.err


def test_open_runs_at_once(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    batch = cli.batch()
    opened: list[Path] = []
    monkeypatch.setattr(actions_module, "_open_folder", opened.append)
    out = cli("open", ".", cwd=batch)
    assert out.code == 0, out
    assert opened == [batch]
    assert out.out.startswith("ok: Opened")


def test_apply_a_new_batch(cli: Cli) -> None:
    out = cli("--json", "new-batch", "Drone", "--date", "2027-01", "--title", "Fly")
    assert _ok(out)["result"]["kind"] == "plan"
    assert not (cli.roots.darkroom / "Drone").exists()
    out = cli(
        "--json", "new-batch", "Drone", "--date", "2027-01", "--title", "Fly", "--apply"
    )
    result = _ok(out)["result"]
    assert result["outcome"] == "ok"
    assert result["node_id"] == "Drone/2027/2027-01 Fly"
    assert (cli.roots.darkroom / "Drone/2027/2027-01 Fly/PUBLISH").is_dir()


def test_apply_tidy(cli: Cli) -> None:
    batch = cli.batch("a.jpg", "b.mp4")
    out = cli("tidy", ".", "--apply", cwd=batch)
    assert out.code == 0, out
    assert out.out.startswith("ok: Tidied 2 of 2 file(s)")
    assert (batch / "PHOTOS/a.jpg").is_file()
    assert (batch / "VIDEOS/b.mp4").is_file()


def test_apply_rename(cli: Cli) -> None:
    cli.batch()
    preview = cli("rename", f"id:{BATCH}", "--title", "Hike")
    assert "Rename 2026-10 Walk to 2026-10 Hike" in preview.out
    assert "--title Hike --confirm" in preview.out
    out = cli(
        "--json",
        *_confirm_argv(cli("--json", "rename", f"id:{BATCH}", "--title", "Hike")),
    )
    result = _ok(out)["result"]
    assert result["node_id"] == "Camera/2026/2026-10 Hike"
    out = cli("rename", "id:Camera/2026/2026-10 Hike", "--no-title", "--apply")
    assert out.code == 0, out
    assert (cli.roots.darkroom / "Camera/2026/2026-10").is_dir()


def test_nothing_to_do_exits_zero(cli: Cli) -> None:
    cli.batch()
    out = cli("--json", "tidy", f"id:{BATCH}")
    assert out.code == 0
    assert out.json()["result"]["outcome"] == "noop"


# ---------------------------------------------------------------------------
# JSON envelope, structured errors, exit codes, no prompts
# ---------------------------------------------------------------------------


def test_not_configured(cli: Cli, tmp_path: Path) -> None:
    out = io.StringIO()
    code = run(
        ["--json", "--config", str(tmp_path / "nowhere.yaml"), "inspect"],
        cwd=cli.home,
        stdout=out,
        stderr=io.StringIO(),
    )
    assert code == 4
    error = json.loads(out.getvalue())["error"]
    assert error["kind"] == "not_ready"
    assert "darkroom" in error["message"]
    assert error["fix"] == "darkroom config set darkroom PATH"


def test_exit_code_failed(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    cli.batch("a.jpg")

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(actions_module, "move_files", boom)
    out = cli("--json", "archive", f"id:{BATCH}", "--apply")
    assert out.code == 1
    assert out.json()["error"]["kind"] == "failed"


def test_exit_code_usage(cli: Cli) -> None:
    assert cli("frobnicate").code == 2
    assert cli("new-batch", "Camera").code == 2


def test_archive_a_year(cli: Cli) -> None:
    cli.batch("a.jpg")
    out = cli("--json", "archive", "id:Camera/2026")
    assert out.code == 3
    error = out.json()["error"]
    assert error["kind"] == "not_allowed"
    assert "open" in error["fix"]


def test_unknown_id(cli: Cli) -> None:
    cli.batch()
    out = cli("inspect", "id:Camera/1999")
    assert out.code == 5
    assert out.out == ""
    assert "Camera/1999" in out.err


def test_refused_prepare_exits_three(cli: Cli) -> None:
    cli.batch()
    out = cli("cull", f"id:{BATCH}")
    assert out.code == 3
    assert "cull_command" in out.out


def test_json_is_one_document_and_logs_stay_off_stdout(cli: Cli) -> None:
    cli.batch("a.jpg")
    out = cli("--json", "-vv", "archive", f"id:{BATCH}", "--apply")
    assert out.code == 0
    assert json.loads(out.out)["command"] == "archive"


def test_apply_without_a_terminal(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    batch = cli.batch("a.jpg")
    closed = io.StringIO()
    closed.close()
    monkeypatch.setattr(sys, "stdin", closed)
    out = cli("archive", ".", "--apply", cwd=batch)
    assert out.code == 0, out
    assert not batch.exists()


# ---------------------------------------------------------------------------
# Conflicts, progress and Ctrl+C
# ---------------------------------------------------------------------------

ARCHIVED = Path("2026/2026-10 Walk/Camera")


def _hundred_with_ten_archived(cli: Cli) -> Path:
    batch = cli.batch(*(f"{i:03}.jpg" for i in range(100)))
    archived = cli.roots.archive / ARCHIVED
    archived.mkdir(parents=True)
    for i in range(0, 100, 10):
        (archived / f"{i:03}.jpg").write_bytes(b"old")
    return batch


def test_preview_with_conflicts(cli: Cli) -> None:
    batch = _hundred_with_ten_archived(cli)
    out = cli("archive", ".", cwd=batch)
    assert out.code == 0
    assert "Archive 90 files, 10 already in the archive" in out.out
    assert "Conflicts (conflict): 10" in out.out
    assert "conflict 000.jpg → 000.jpg" in out.out
    plan = _ok(cli("--json", "archive", ".", "--on-conflict", "skip", cwd=batch))
    assert len(plan["result"]["conflicts"]) == 10
    assert plan["result"]["confirm"][-4:-2] == ["--on-conflict", "skip"]


def test_conflicts_without_an_option(cli: Cli) -> None:
    batch = _hundred_with_ten_archived(cli)
    out = cli("--json", "archive", ".", "--apply", cwd=batch)
    assert out.code == 3
    document = out.json()
    assert document["error"]["kind"] == "refused"
    assert len(document["result"]["conflicts"]) == 10
    assert len(list(batch.iterdir())) == 100


def test_archive_skipping_conflicts(cli: Cli) -> None:
    batch = _hundred_with_ten_archived(cli)
    out = cli("archive", ".", "--apply", "--on-conflict", "skip", cwd=batch)
    assert out.code == 0, out
    assert "skipped: 10 conflict(s)" in out.out
    assert len(list(batch.iterdir())) == 10
    assert len(list((cli.roots.archive / ARCHIVED).iterdir())) == 100


def test_confirm_carries_the_conflict_option(cli: Cli) -> None:
    batch = _hundred_with_ten_archived(cli)
    argv = _confirm_argv(
        cli("--json", "archive", ".", "--on-conflict", "skip", cwd=batch)
    )
    out = cli(*argv)
    assert out.code == 0, out
    assert len(out.json()["result"]["skipped"]) == 10


def test_replace_on_archive_is_a_usage_error(cli: Cli) -> None:
    batch = cli.batch("a.jpg")
    out = cli("--json", "archive", ".", "--on-conflict", "replace", cwd=batch)
    assert out.code == 2
    assert out.json()["error"]["kind"] == "usage"
    assert (
        cli("archive", ".", "--apply", "--on-conflict", "replace", cwd=batch).code == 2
    )
    assert cli("rename", f"id:{BATCH}", "--on-conflict", "skip").code == 2


def test_republish_needs_a_choice(cli: Cli) -> None:
    batch = cli.batch("PUBLISH/a.jpg", "PUBLISH/b.jpg")
    showroom = cli.roots.showroom / ARCHIVED
    showroom.mkdir(parents=True)
    (showroom / "a.jpg").write_bytes(b"old")
    assert cli("publish", ".", "--apply", cwd=batch).code == 3
    assert (showroom / "a.jpg").read_bytes() == b"old"
    out = cli("publish", ".", "--apply", "--on-conflict", "replace", cwd=batch)
    assert out.code == 0, out
    assert (showroom / "a.jpg").read_bytes() == b"PUBLISH/a.jpg"
    assert list((batch / "PUBLISH").iterdir()) == []


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _run_with_stderr(cli: Cli, stderr: io.StringIO, *argv: str, cwd: Path) -> int:
    return run(
        ["--config", str(cli.config), *argv],
        cwd=cwd,
        stdout=io.StringIO(),
        stderr=stderr,
    )


def test_agent_run_writes_one_document_and_no_progress(cli: Cli) -> None:
    batch = cli.batch("a.jpg", "b.jpg")
    out = cli("--json", "archive", ".", "--apply", cwd=batch)
    assert out.code == 0
    assert json.loads(out.out)["result"]["outcome"] == "ok"
    assert "\r" not in out.err


def test_progress_on_a_terminal(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    batch = cli.batch("a.jpg", "b.jpg")
    monkeypatch.setattr(app_module, "_WAIT_STEP_S", 0.001)
    real = file_utils.move_file

    def slow(src: Path, dst: Path, *, replace: bool = False) -> None:
        time.sleep(0.05)
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", slow)
    stderr = _Terminal()
    code = _run_with_stderr(cli, stderr, "archive", ".", "--apply", cwd=batch)
    assert code == 0
    drawn = stderr.getvalue()
    assert f"\rarchive {BATCH}: " in drawn
    assert drawn.endswith("\r")


def test_ctrl_c_cancels_the_job(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    batch = cli.batch(*(f"{i:03}.jpg" for i in range(10)))
    reached = threading.Event()
    release = threading.Event()
    real_move = file_utils.move_file
    moved = 0

    def gated(src: Path, dst: Path, *, replace: bool = False) -> None:
        nonlocal moved
        if moved == 3:
            reached.set()
            assert release.wait(5)
        real_move(src, dst, replace=replace)
        moved += 1

    monkeypatch.setattr(file_utils, "move_file", gated)
    real_wait = Engine.job_wait
    real_cancel = Engine.job_cancel

    def interrupted(self: Engine, timeout: float | None = None):
        if timeout is not None:
            assert reached.wait(5)
            raise KeyboardInterrupt
        return real_wait(self, timeout)

    def cancel(self: Engine) -> None:
        real_cancel(self)
        release.set()

    monkeypatch.setattr(Engine, "job_wait", interrupted)
    monkeypatch.setattr(Engine, "job_cancel", cancel)
    out = cli("--json", "archive", ".", "--apply", cwd=batch)

    assert out.code == 130
    result = out.json()["result"]
    assert result["outcome"] == "cancelled"
    assert len(result["done"]) == 4
    assert len(result["left"]) == 6
    assert len(list((cli.roots.archive / ARCHIVED).iterdir())) == 4


def test_archive_reports_the_files_remaining(
    cli: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = cli.batch("a.jpg", "b.jpg")
    real = file_utils.move_file

    def locked(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "b.jpg":
            raise PermissionError("locked")
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", locked)
    out = cli("--json", "archive", ".", "--apply", cwd=batch)
    assert out.code == 1, out
    result = out.json()["result"]
    assert result["outcome"] == "failed"
    assert result["left"] == []
    assert [Path(p).name for p in result["remaining"]] == ["b.jpg"]

    text = cli("archive", ".", "--apply", cwd=batch)
    assert "remaining: 1 file(s)" in text.out
    assert "left:" not in text.out


# ---------------------------------------------------------------------------
# Rename and new batch run at once
# ---------------------------------------------------------------------------


def test_rename_and_new_batch_show_no_progress_and_leave_no_job_log(
    cli: Cli, tmp_path: Path
) -> None:
    cli.batch()
    rename = ("rename", f"id:{BATCH}", "--title", "Hike", "--apply")
    new_batch = ("new-batch", "Drone", "--date", "2027-01", "--apply")
    for argv in (rename, new_batch):
        stderr = _Terminal()
        assert _run_with_stderr(cli, stderr, *argv, cwd=cli.home) == 0
        assert "\r" not in stderr.getvalue()
    assert (cli.roots.darkroom / "Camera/2026/2026-10 Hike").is_dir()
    assert (cli.roots.darkroom / "Drone/2027/2027-01").is_dir()
    assert not (tmp_path / "logs" / "jobs").exists()


def test_a_busy_engine_refuses_rename_and_new_batch(
    cli: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = cli.batch("a.jpg", "b.jpg")
    other = "Camera/2026/2026-11 Hike"
    cli.batch(node_id=other)
    reached = threading.Event()
    release = threading.Event()
    real_move = file_utils.move_file

    def gated(src: Path, dst: Path, *, replace: bool = False) -> None:
        reached.set()
        assert release.wait(5)
        real_move(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", gated)
    engine = Engine(cli.config)
    engine.action_start(engine.action_archive(BATCH))
    try:
        assert reached.wait(5)
        for argv in (
            ("rename", f"id:{other}", "--title", "Walk", "--apply"),
            ("new-batch", "Drone", "--date", "2027-01", "--apply"),
        ):
            out = io.StringIO()
            code = run(
                ["--config", str(cli.config), "--json", *argv],
                cwd=cli.home,
                stdout=out,
                stderr=io.StringIO(),
                make_engine=lambda *_: engine,
            )
            assert code == 3
            error = json.loads(out.getvalue())["error"]
            assert error["kind"] == "busy"
            assert f"archive {BATCH}" in error["message"]
    finally:
        release.set()
        engine.job_wait(5)
    assert (cli.roots.darkroom / other).is_dir()
    assert not (cli.roots.darkroom / "Drone").exists()
    assert not batch.exists()
