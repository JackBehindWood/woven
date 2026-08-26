from __future__ import annotations

import uuid
from collections.abc import Callable

import typer
from rich.console import Console

from woven.client.cli.console import make_console
from woven.client.cli.render import (
    render_banner,
    render_error,
    render_header,
    render_help,
    render_hint,
)
from woven.client.cli.session import run_chat_turn
from woven.models import FakeModel
from woven.runtime import AgentRun, AgentRuntime

app = typer.Typer(
    name="woven",
    help="Woven — a local-first AI agent platform. This is an early CLI slice.",
    add_completion=False,
)

DEFAULT_RESPONSE = "This is a fixed demo reply — Woven has no real model connected yet."
_EXIT_WORDS = {"exit", "quit", ":q"}


def _handle_help(console: Console, response: str) -> None:
    render_help(
        console,
        {name: description for name, (description, _) in _COMMANDS.items()},
        sorted(_EXIT_WORDS),
    )


def _handle_clear(console: Console, response: str) -> None:
    console.clear()
    render_banner(console)
    render_header(console, response_text=response)
    render_hint(console)


# Add a REPL command by adding one entry here — name -> (description, handler).
_COMMANDS: dict[str, tuple[str, Callable[[Console, str], None]]] = {
    "/help": ("List available commands", _handle_help),
    "/clear": ("Clear the screen and redraw the header", _handle_clear),
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
) -> None:
    """Start an interactive chat session against the built-in `chat` mode.

    This uses FakeModel — a deterministic stand-in with a fixed reply — since
    Woven has no real model provider implemented yet. See --response to
    change the canned reply.
    """
    _run_chat(response)


def _run_chat(response: str) -> None:
    console = make_console()
    console.set_window_title("Woven")
    console.clear()
    render_banner(console)
    render_header(console, response_text=response)
    render_hint(console)

    runtime = AgentRuntime()
    run = AgentRun(run_id=uuid.uuid4().hex)
    model = FakeModel(response_text=response)

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
            command = _COMMANDS.get(stripped.lower())
            if command is None:
                render_error(
                    console, f"Unknown command: {stripped}. Type /help for a list."
                )
            else:
                _, handler = command
                handler(console, response)
            continue

        run_chat_turn(runtime, run, "chat", user_input, model, console)
        console.rule(style="woven.dim")
