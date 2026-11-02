"""The ``darkroom`` command line: parser, dispatch, output and exit codes.

Every command parses its input, calls the engine and renders what comes
back; no domain rule is decided here.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from photo_darkroom_manager.cli import _render
from photo_darkroom_manager.cli._targets import (
    ID_PREFIX,
    AmbiguousTargetError,
    default_target,
    resolve,
)
from photo_darkroom_manager.core.actions import (
    Action,
    ActionPlan,
    ExecutionResult,
)
from photo_darkroom_manager.core.engine import (
    ROOT_KEYS,
    ActionNotAllowedError,
    Engine,
    EngineBusyError,
    EngineNotReadyError,
    NodeNotFoundError,
    PathOutsideDarkroomError,
)
from photo_darkroom_manager.core.library import NodeId, node_actions
from photo_darkroom_manager.core.user_config import (
    ConfigValueError,
    LogLevel,
    UnknownConfigKeyError,
)

PROG = "darkroom"
FORMAT_VERSION = 1

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_NOT_READY = 4
EXIT_NOT_FOUND = 5

_OUTCOME_EXIT = {"ok": EXIT_OK, "noop": EXIT_OK, "refused": EXIT_REFUSED}

MakeEngine = Callable[[Path | None, LogLevel], Engine]


def default_engine(config_path: Path | None, console_level: LogLevel) -> Engine:
    return Engine(config_path, console_log_level=console_level)


@dataclass
class Reply:
    """What a command prints: one JSON document, or text, and an exit code."""

    code: int
    result: object = None
    text: str = ""
    error: dict[str, object] | None = None


@dataclass
class _Context:
    args: argparse.Namespace
    engine: Engine
    cwd: Path

    def target(self) -> NodeId:
        return resolve(self.args.target, self.cwd, self.engine)


class CliError(Exception):
    """A refusal or failure with an exit code, a kind and maybe a fix."""

    def __init__(
        self, code: int, kind: str, message: str, fix: str | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind
        self.message = message
        self.fix = fix


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    run = parser.add_mutually_exclusive_group()
    run.add_argument(
        "--apply", action="store_true", help="run the action as it is prepared now"
    )
    run.add_argument(
        "--confirm",
        metavar="FINGERPRINT",
        help="run the action only if its plan still has this fingerprint",
    )


_TARGET_HELP = (
    "node id (id:Camera/2026) or a path in the darkroom; a bare name is tried as both"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Manage the photo darkroom: inspect nodes and run node actions. "
            "Commands that change files only preview them unless given "
            "--apply or --confirm."
        ),
    )
    parser.add_argument("--json", action="store_true", help="print one JSON document")
    parser.add_argument("--config", metavar="PATH", help="configuration file to use")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="log more on stderr (-v info, -vv debug)",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    commands.add_parser("status", help="show whether the engine is ready and why")

    config = commands.add_parser("config", help="list, read or change settings")
    config_commands = config.add_subparsers(
        dest="config_command", metavar="ACTION", required=True
    )
    config_commands.add_parser("list", help="show every setting and its problems")
    get = config_commands.add_parser("get", help="show one setting")
    get.add_argument("key")
    set_ = config_commands.add_parser("set", help="validate, store and save a value")
    set_.add_argument("key")
    set_.add_argument("value")

    inspect = commands.add_parser(
        "inspect", help="show a node, its files, issues, actions and children"
    )
    inspect.add_argument(
        "target",
        nargs="?",
        help=_TARGET_HELP + "; default: the current folder, or the root",
    )
    inspect.add_argument(
        "--depth",
        type=int,
        default=1,
        metavar="N",
        help="levels of children to show (default 1)",
    )

    for name, text in (
        ("open", "show the node's folder in the file manager"),
        ("cull", "open the batch in the configured cull_command"),
        ("edit", "open the batch in the configured edit_command"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("target", help=_TARGET_HELP)
        _add_run_options(command)

    for name, text in (
        ("tidy", "move misplaced photos and videos into PHOTOS/ and VIDEOS/"),
        ("publish", "move a batch's PUBLISH/ files to the showroom"),
        ("archive", "move a batch or subfolder's files to the archive"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("target", help=_TARGET_HELP)
        _add_run_options(command)

    rename = commands.add_parser(
        "rename", help="rename a batch; an omitted date or title is kept"
    )
    rename.add_argument("target", help=_TARGET_HELP)
    rename.add_argument("--date", metavar="YYYY-MM[-DD]", help="new date")
    title = rename.add_mutually_exclusive_group()
    title.add_argument("--title", help="new title")
    title.add_argument("--no-title", action="store_true", help="drop the title")
    _add_run_options(rename)

    new_batch = commands.add_parser(
        "new-batch", help="create a batch (and its device and year) for a device"
    )
    new_batch.add_argument("target", help="device: " + _TARGET_HELP)
    new_batch.add_argument(
        "--date", required=True, metavar="YYYY-MM[-DD]", help="batch date"
    )
    new_batch.add_argument("--title", help="batch title")
    _add_run_options(new_batch)
    return parser


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _status(ctx: _Context) -> Reply:
    engine = ctx.engine
    roots = {key: _render.value_data(getattr(engine, key)) for key in ROOT_KEYS}
    issues = engine.status_issues
    data = {
        "status": engine.status,
        "detail": engine.status_detail,
        "config_path": str(engine.config_path),
        "roots": roots,
        "issues": _render.issues_data(issues),
    }
    lines = [f"status: {engine.status}", f"config: {engine.config_path}"]
    lines += [f"{key}: {_render.value_text(value)}" for key, value in roots.items()]
    if issues:
        lines.append("issues:")
        lines += _render.issues_text(issues)
    return Reply(EXIT_OK, data, "\n".join(lines))


def _config(ctx: _Context) -> Reply:
    args, engine = ctx.args, ctx.engine
    if args.config_command == "list":
        values = {
            k: _render.value_data(engine.config_get(k)) for k in engine.config_keys()
        }
        issues = engine.config_issues
        lines = [f"{k}: {_render.value_text(v)}" for k, v in values.items()]
        if issues:
            lines.append("issues:")
            lines += _render.issues_text(issues)
        data = {"values": values, "issues": _render.issues_data(issues)}
        return Reply(EXIT_OK, data, "\n".join(lines))
    if args.config_command == "get":
        value = engine.config_get(args.key)
        data = {"key": args.key, "value": _render.value_data(value)}
        return Reply(EXIT_OK, data, _render.value_text(value))
    value: object = args.value
    if args.key in ROOT_KEYS:
        value = ctx.cwd / Path(args.value).expanduser()
    engine.config_set(args.key, value)
    saved = engine.config_save()
    stored = engine.config_get(args.key)
    data = {"key": args.key, "value": _render.value_data(stored), "saved": str(saved)}
    return Reply(
        EXIT_OK, data, f"{args.key}: {_render.value_text(stored)}\nsaved: {saved}"
    )


def _inspect(ctx: _Context) -> Reply:
    args, engine = ctx.args, ctx.engine
    target = args.target
    requested = default_target(ctx.cwd, engine) if target is None else ctx.target()
    node_id = engine.library_scan(requested)
    view = engine.library_node(node_id)
    depth = max(args.depth, 0)
    return Reply(
        EXIT_OK, _render.view_data(view, depth), _render.view_text(view, depth)
    )


def _quote(arg: str) -> str:
    if arg and all(c.isalnum() or c in "-_./:=" for c in arg):
        return arg
    return '"' + arg.replace('"', '\\"') + '"'


def _confirm_argv(args: argparse.Namespace, node_id: NodeId, fp: str) -> list[str]:
    argv = [PROG]
    if args.json:
        argv.append("--json")
    if args.config:
        argv += ["--config", args.config]
    argv += [args.command, ID_PREFIX + node_id]
    if getattr(args, "date", None):
        argv += ["--date", args.date]
    if getattr(args, "title", None) is not None:
        argv += ["--title", args.title]
    if getattr(args, "no_title", False):
        argv.append("--no-title")
    return [*argv, "--confirm", fp]


def _result_reply(result: ExecutionResult) -> Reply:
    code = _OUTCOME_EXIT.get(result.outcome, EXIT_FAILED)
    error: dict[str, object] | None = None
    if code != EXIT_OK:
        error = {"kind": result.outcome, "message": result.message}
        if result.outcome == "refused" and result.fingerprint is not None:
            error["fix"] = "preview again, then confirm the new plan"
    return Reply(code, _render.result_data(result), _render.result_text(result), error)


def _action_factory(ctx: _Context) -> Callable[[NodeId], Action]:
    args, engine = ctx.args, ctx.engine
    simple: dict[str, Callable[[NodeId], Action]] = {
        "open": engine.action_open,
        "tidy": engine.action_tidy,
        "cull": engine.action_cull,
        "edit": engine.action_edit,
        "publish": engine.action_publish,
        "archive": engine.action_archive,
    }
    if args.command in simple:
        return simple[args.command]
    if args.command == "rename":
        return lambda node_id: engine.action_rename(
            node_id, date=args.date, title=args.title, clear_title=args.no_title
        )
    return lambda node_id: engine.action_new_batch(
        node_id, date=args.date, title=args.title
    )


def _action(ctx: _Context) -> Reply:
    args, engine = ctx.args, ctx.engine
    action = _action_factory(ctx)(ctx.target())
    node_id = action.request.node_id
    if args.apply or args.confirm is not None:
        return _result_reply(engine.action_apply(action, confirm=args.confirm))

    prepared = action.prepare()
    if not isinstance(prepared, ActionPlan):
        result = ExecutionResult(prepared.outcome, prepared.message, prepared.details)
        return _result_reply(result)
    if not prepared.changes_files:
        return _result_reply(engine.action_execute(action, prepared))
    confirm = _confirm_argv(args, node_id, prepared.fingerprint)
    return Reply(
        EXIT_OK,
        _render.plan_data(prepared, confirm),
        _render.plan_text(prepared, " ".join(_quote(a) for a in confirm)),
    )


_COMMANDS: dict[str, Callable[[_Context], Reply]] = {
    "status": _status,
    "config": _config,
    "inspect": _inspect,
    **{
        name: _action
        for name in (
            "open",
            "tidy",
            "cull",
            "edit",
            "rename",
            "publish",
            "archive",
            "new-batch",
        )
    },
}


# ---------------------------------------------------------------------------
# Errors and output
# ---------------------------------------------------------------------------


def _not_ready(engine: Engine, error: EngineNotReadyError) -> CliError:
    issues = engine.status_issues
    message = f"engine is {error.status}: {error.detail}"
    if issues and issues[0].key in engine.config_keys():
        key = issues[0].key
        value = "PATH" if key in ROOT_KEYS else "VALUE"
        message = f"{message} (fix {key!r} first)"
        return CliError(
            EXIT_NOT_READY, "not_ready", message, f"{PROG} config set {key} {value}"
        )
    return CliError(EXIT_NOT_READY, "not_ready", message, f"{PROG} status")


def _as_cli_error(engine: Engine, error: Exception) -> CliError | None:
    match error:
        case EngineNotReadyError():
            return _not_ready(engine, error)
        case NodeNotFoundError():
            return CliError(
                EXIT_NOT_FOUND,
                "not_found",
                f"no library node {error.node_id!r}",
                f"{PROG} inspect to see the nodes",
            )
        case PathOutsideDarkroomError():
            return CliError(
                EXIT_NOT_FOUND,
                "outside_darkroom",
                f"{error.path} is outside the darkroom {error.root}",
            )
        case ActionNotAllowedError():
            allowed = ", ".join(sorted(node_actions(error.kind)))
            return CliError(
                EXIT_REFUSED,
                "not_allowed",
                str(error),
                f"actions for a {error.kind}: {allowed}",
            )
        case AmbiguousTargetError():
            return CliError(
                EXIT_REFUSED,
                "ambiguous",
                str(error),
                f"use {ID_PREFIX}{error.as_id} or ./{error.text}",
            )
        case EngineBusyError():
            return CliError(EXIT_REFUSED, "busy", str(error))
        case ConfigValueError():
            return CliError(EXIT_REFUSED, "invalid_value", str(error))
        case UnknownConfigKeyError():
            return CliError(
                EXIT_REFUSED, "unknown_key", str(error), f"{PROG} config list"
            )
    return None


def _emit(
    reply: Reply, command: str, as_json: bool, stdout: TextIO, stderr: TextIO
) -> None:
    if as_json:
        document: dict[str, object] = {
            "format": FORMAT_VERSION,
            "command": command,
            "ok": reply.code == EXIT_OK,
        }
        if reply.result is not None:
            document["result"] = reply.result
        if reply.error is not None:
            document["error"] = reply.error
        stdout.write(json.dumps(document, indent=2) + "\n")
        return
    if reply.text:
        stdout.write(reply.text + "\n")
    if reply.error is not None and reply.result is None:
        stderr.write(f"error: {reply.error['message']}\n")
        if "fix" in reply.error:
            stderr.write(f"fix: {reply.error['fix']}\n")


def _console_level(verbose: int) -> LogLevel:
    return "WARNING" if verbose <= 0 else "INFO" if verbose == 1 else "DEBUG"


def _command_name(args: argparse.Namespace) -> str:
    if args.command == "config":
        return f"config {args.config_command}"
    return args.command


def run(
    argv: Sequence[str],
    *,
    cwd: Path,
    stdout: TextIO,
    stderr: TextIO,
    make_engine: MakeEngine = default_engine,
) -> int:
    """Run one command; return its exit code. Never reads input."""
    parser = build_parser()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            args = parser.parse_args(list(argv))
    except SystemExit as exit_:
        return EXIT_OK if exit_.code in (0, None) else EXIT_USAGE

    config_path = cwd / Path(args.config).expanduser() if args.config else None
    engine = make_engine(config_path, _console_level(args.verbose))
    ctx = _Context(args, engine, cwd)
    try:
        reply = _COMMANDS[args.command](ctx)
    except Exception as error:
        cli_error = _as_cli_error(engine, error)
        if cli_error is None:
            raise
        info: dict[str, object] = {"kind": cli_error.kind, "message": cli_error.message}
        if cli_error.fix is not None:
            info["fix"] = cli_error.fix
        reply = Reply(cli_error.code, error=info)
    _emit(reply, _command_name(args), args.json, stdout, stderr)
    return reply.code
