from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from woven import __version__
from woven.events import (
    Event,
    ModelCompleted,
    ModelStarted,
    RunCompleted,
    RunFailed,
    RunStarted,
    TurnCompleted,
    TurnStarted,
)


def render_header(console: Console, *, response_text: str) -> None:
    console.print(
        Panel(
            f"[bold cyan]Woven[/bold cyan] [dim]v{__version__}[/dim] · chat\n"
            f"[dim]workspace:[/dim] {Path.cwd()}  "
            f"[dim](current directory — Woven has no project/workspace "
            f"concept yet)[/dim]\n"
            f"[yellow]demo model:[/yellow] FakeModel — every message gets "
            f'this same fixed reply: "{response_text}"',
            box=box.ROUNDED,
            border_style="cyan",
            title="woven chat",
            title_align="left",
        )
    )


def render_error(console: Console, message: str) -> None:
    console.print(
        Panel(
            f"[bold red]{message}[/bold red]",
            box=box.ROUNDED,
            border_style="red",
            title="error",
            title_align="left",
        )
    )


def _render_run_started(event: RunStarted, console: Console) -> None:
    return


def _render_turn_started(event: TurnStarted, console: Console) -> None:
    return


def _render_model_started(event: ModelStarted, console: Console) -> None:
    console.print("  [cyan]◌[/cyan] [dim]Calling model…[/dim]")


def _render_model_completed(event: ModelCompleted, console: Console) -> None:
    console.print("  [green]✓[/green] [dim]Model responded[/dim]")


def _render_turn_completed(event: TurnCompleted, console: Console) -> None:
    console.print(
        Panel(
            Markdown(event.output_text),
            box=box.ROUNDED,
            title="[bold green]woven[/bold green]",
            title_align="left",
            border_style="green",
        )
    )


def _render_run_completed(event: RunCompleted, console: Console) -> None:
    return


def _render_run_failed(event: RunFailed, console: Console) -> None:
    render_error(console, f"Turn failed: {event.error}")


def _render_unknown(event: Event, console: Console) -> None:
    console.print(f"  [dim]· {type(event).__name__}[/dim]")


_RENDERERS: dict[type[Event], Callable[[Event, Console], None]] = {
    RunStarted: _render_run_started,
    TurnStarted: _render_turn_started,
    ModelStarted: _render_model_started,
    ModelCompleted: _render_model_completed,
    TurnCompleted: _render_turn_completed,
    RunCompleted: _render_run_completed,
    RunFailed: _render_run_failed,
}


def render_event(event: Event, console: Console) -> None:
    _RENDERERS.get(type(event), _render_unknown)(event, console)
