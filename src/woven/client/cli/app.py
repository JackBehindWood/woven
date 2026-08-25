from __future__ import annotations

import uuid

import typer
from rich.console import Console

from woven.client.cli.render import render_header
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


@app.callback()
def main() -> None:
    """Woven — a local-first AI agent platform. This is an early CLI slice."""


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
    console = Console()
    render_header(console, response_text=response)

    runtime = AgentRuntime()
    run = AgentRun(run_id=uuid.uuid4().hex)
    model = FakeModel(response_text=response)

    while True:
        try:
            user_input = console.input("[bold cyan]you[/bold cyan] › ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            raise typer.Exit(code=0) from None

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped.lower() in _EXIT_WORDS:
            console.print("[dim]Goodbye.[/dim]")
            raise typer.Exit(code=0)

        run_chat_turn(runtime, run, "chat", user_input, model, console)
        console.rule(style="dim")
