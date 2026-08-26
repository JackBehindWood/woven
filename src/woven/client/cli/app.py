from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import typer
from rich.console import Console

from woven.client.cli.approval import InteractiveApprovalPolicy
from woven.client.cli.console import make_console
from woven.client.cli.render import (
    render_banner,
    render_error,
    render_header,
    render_help,
    render_hint,
    render_status_panel,
)
from woven.client.cli.session import run_chat_turn
from woven.context import ContextRequest, FilesystemContext
from woven.models import FakeModel
from woven.modes import BUILTIN_MODES
from woven.permissions import ApprovalPolicy, AutoApprovalPolicy
from woven.runtime import AgentRun, AgentRuntime
from woven.tools import MockTools

app = typer.Typer(
    name="woven",
    help="Woven — a local-first AI agent platform. This is an early CLI slice.",
    add_completion=False,
)

DEFAULT_RESPONSE = "This is a fixed demo reply — Woven has no real model connected yet."
_EXIT_WORDS = {"exit", "quit", ":q"}
_PERMISSION_MODES: tuple[str, ...] = ("auto", "guarded", "manual")

# Modes that get real (non-mock) context retrieval / tool access / approval
# gating in the CLI — kept in one place so `_run_chat`'s per-turn wiring and
# these sets can't drift out of sync with each other.
_MODES_WITH_TOOL = {"code"}
_MODES_WITH_CONTEXT = {"plan", "code"}
_MODES_WITH_APPROVAL = {"code"}


@dataclass
class SessionState:
    response: str
    mode_name: str = "chat"
    permission_mode: str = "guarded"
    context_request: ContextRequest = field(
        default_factory=lambda: ContextRequest(purpose="context_retrieval")
    )


def _handle_help(console: Console, state: SessionState, argument: str) -> None:
    render_help(
        console,
        {name: description for name, (description, _) in _COMMANDS.items()},
        sorted(_EXIT_WORDS),
    )


def _handle_clear(console: Console, state: SessionState, argument: str) -> None:
    console.clear()
    render_banner(console)
    render_header(console, response_text=state.response, mode_name=state.mode_name)
    render_hint(console)


def _handle_mode(console: Console, state: SessionState, argument: str) -> None:
    available = ", ".join(sorted(BUILTIN_MODES))
    name = argument.strip()
    if not name:
        render_status_panel(
            console,
            "mode",
            [f"current: {state.mode_name}", f"available: {available}"],
        )
        return
    if name not in BUILTIN_MODES:
        render_error(console, f"Unknown mode: {name}. Available: {available}")
        return
    state.mode_name = name
    render_status_panel(console, "mode", [f"switched to: {name}"])


def _handle_permission(console: Console, state: SessionState, argument: str) -> None:
    name = argument.strip()
    if not name:
        lines = [f"current: {state.permission_mode}"]
        lines.extend(
            f"{m} (default)" if m == "guarded" else m for m in _PERMISSION_MODES
        )
        render_status_panel(console, "permission", lines)
        return
    if name not in _PERMISSION_MODES:
        render_error(
            console,
            f"Unknown permission mode: {name}. "
            f"Available: {', '.join(_PERMISSION_MODES)}",
        )
        return
    state.permission_mode = name
    render_status_panel(console, "permission", [f"switched to: {name}"])


def _context_status_lines(request: ContextRequest) -> list[str]:
    return [
        f"paths: {request.paths or '(none)'}",
        f"glob: {request.name_glob or '(none)'}",
        f"query: {request.text_query or '(none)'}",
    ]


def _handle_context(console: Console, state: SessionState, argument: str) -> None:
    sub, _, rest = argument.strip().partition(" ")
    rest = rest.strip()

    if not sub or sub == "show":
        render_status_panel(
            console, "context", _context_status_lines(state.context_request)
        )
        return
    if sub == "clear":
        state.context_request = ContextRequest(purpose="context_retrieval")
        render_status_panel(console, "context", ["cleared"])
        return
    if sub == "path" and rest:
        state.context_request = state.context_request.model_copy(
            update={"paths": [*state.context_request.paths, rest]}
        )
        render_status_panel(
            console, "context", _context_status_lines(state.context_request)
        )
        return
    if sub == "glob" and rest:
        state.context_request = state.context_request.model_copy(
            update={"name_glob": rest}
        )
        render_status_panel(
            console, "context", _context_status_lines(state.context_request)
        )
        return
    if sub == "query" and rest:
        state.context_request = state.context_request.model_copy(
            update={"text_query": rest}
        )
        render_status_panel(
            console, "context", _context_status_lines(state.context_request)
        )
        return

    render_error(console, "Usage: /context [path <p>|glob <g>|query <q>|clear|show]")


def _handle_settings(console: Console, state: SessionState, argument: str) -> None:
    lines = [
        f"mode: {state.mode_name}",
        f"permission: {state.permission_mode}",
        *_context_status_lines(state.context_request),
    ]
    render_status_panel(console, "settings", lines)


# Add a REPL command by adding one entry here — name -> (description, handler).
_COMMANDS: dict[str, tuple[str, Callable[[Console, SessionState, str], None]]] = {
    "/help": ("List available commands", _handle_help),
    "/clear": ("Clear the screen and redraw the header", _handle_clear),
    "/settings": (
        "Show all current session settings (mode, permission, context)",
        _handle_settings,
    ),
    "/mode": ("Show or switch the active mode (chat/plan/code)", _handle_mode),
    "/permission": (
        "Show or switch the tool-approval tier (auto/guarded/manual)",
        _handle_permission,
    ),
    "/context": (
        "Show or edit the context request (path/glob/query/clear/show)",
        _handle_context,
    ),
}


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Woven — a local-first AI agent platform. This is an early CLI slice."""
    if ctx.invoked_subcommand is None:
        _run_chat(DEFAULT_RESPONSE)


@app.command()
def chat(
    response: str = typer.Option(
        DEFAULT_RESPONSE,
        "--response",
        "-r",
        help="Fixed text the demo model replies with (no real model is connected yet).",
    ),
    mode: str = typer.Option(
        "chat",
        "--mode",
        "-m",
        help="Mode to run the session in: chat, plan, or code.",
    ),
    permission_mode: str = typer.Option(
        "guarded",
        "--permission-mode",
        help="Tool-approval tier: auto, guarded (default), or manual.",
    ),
) -> None:
    """Start an interactive chat session against a built-in Mode.

    This uses FakeModel — a deterministic stand-in with a fixed reply — since
    Woven has no real model provider implemented yet. See --response to
    change the canned reply, --mode to pick chat/plan/code, and
    --permission-mode to pick the tool-approval tier.
    """
    _run_chat(response, mode=mode, permission_mode=permission_mode)


def _run_chat(
    response: str, *, mode: str = "chat", permission_mode: str = "guarded"
) -> None:
    console = make_console()

    if mode not in BUILTIN_MODES:
        render_error(
            console,
            f"Unknown mode: {mode}. Available: {', '.join(sorted(BUILTIN_MODES))}",
        )
        raise typer.Exit(code=1)
    if permission_mode not in _PERMISSION_MODES:
        render_error(
            console,
            f"Unknown permission mode: {permission_mode}. "
            f"Available: {', '.join(_PERMISSION_MODES)}",
        )
        raise typer.Exit(code=1)

    console.set_window_title("Woven")
    console.clear()
    render_banner(console)
    render_header(console, response_text=response, mode_name=mode)
    render_hint(console)

    state = SessionState(
        response=response, mode_name=mode, permission_mode=permission_mode
    )

    runtime = AgentRuntime()
    run = AgentRun(run_id=uuid.uuid4().hex)
    model = FakeModel(response_text=response)
    tool = MockTools()
    context_source = FilesystemContext(root=Path.cwd())
    approval_policies: dict[str, ApprovalPolicy] = {
        "auto": AutoApprovalPolicy(),
        "guarded": InteractiveApprovalPolicy(console, always_prompt=False),
        "manual": InteractiveApprovalPolicy(console, always_prompt=True),
    }

    while True:
        try:
            user_input = console.input("[woven.accent]you[/woven.accent] › ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[woven.dim]Goodbye.[/woven.dim]")
            raise typer.Exit(code=0) from None

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped.lower() in _EXIT_WORDS:
            console.print("[woven.dim]Goodbye.[/woven.dim]")
            raise typer.Exit(code=0)

        if stripped.startswith("/"):
            command_word, _, argument = stripped.partition(" ")
            command = _COMMANDS.get(command_word.lower())
            if command is None:
                render_error(
                    console,
                    f"Unknown command: {command_word}. Type /help for a list.",
                )
            else:
                _, handler = command
                handler(console, state, argument)
            continue

        run_chat_turn(
            runtime,
            run,
            state.mode_name,
            user_input,
            model,
            console,
            tool=tool if state.mode_name in _MODES_WITH_TOOL else None,
            context_source=(
                context_source if state.mode_name in _MODES_WITH_CONTEXT else None
            ),
            context_request=(
                state.context_request
                if state.mode_name in _MODES_WITH_CONTEXT
                else None
            ),
            approval=(
                approval_policies[state.permission_mode]
                if state.mode_name in _MODES_WITH_APPROVAL
                else None
            ),
        )
        console.rule(style="woven.dim")
