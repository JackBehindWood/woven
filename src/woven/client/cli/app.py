from __future__ import annotations

import uuid

import typer

from woven.client.cli.console import make_console
from woven.client.cli.render import render_banner, render_header, render_hint
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

        run_chat_turn(runtime, run, "chat", user_input, model, console)
        console.rule(style="woven.dim")
