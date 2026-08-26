from __future__ import annotations

from collections.abc import Callable, Iterable
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


def render_banner(console: Console) -> None:
    console.print("[woven.accent]W O V E N[/woven.accent]", justify="center")


def render_header(console: Console, *, response_text: str) -> None:
    console.print(
        Panel(
            f"[woven.accent]Woven[/woven.accent] [woven.dim]v{__version__}[/woven.dim] · chat\n"
            f"[woven.dim]workspace:[/woven.dim] {Path.cwd()}  "
            f"[woven.dim](current directory — Woven has no project/workspace "
            f"concept yet)[/woven.dim]\n"
            f"[woven.warning]demo model:[/woven.warning] FakeModel — every "
            f'message gets this same fixed reply: "{response_text}"',
            box=box.ROUNDED,
            border_style="woven.accent",
            title="woven chat",
            title_align="left",
        )
    )


def render_hint(console: Console) -> None:
    console.print(
        "[woven.dim]Type exit, quit, or :q to leave. Type /help for more commands.[/woven.dim]"
    )


def render_error(console: Console, message: str) -> None:
    console.print(
        Panel(
            f"[woven.error]{message}[/woven.error]",
            box=box.ROUNDED,
            border_style="woven.error",
            title="error",
            title_align="left",
        )
    )


def render_help(
    console: Console, commands: dict[str, str], exit_words: Iterable[str]
) -> None:
    lines = [
        f"[woven.accent]{name}[/woven.accent]  {description}"
        for name, description in commands.items()
    ]
    lines.append(
        f"[woven.accent]{', '.join(exit_words)}[/woven.accent]  Leave the session"
    )
    console.print(
        Panel(
            "\n".join(lines),
            box=box.ROUNDED,
            border_style="woven.accent",
            title="commands",
            title_align="left",
        )
    )


def _render_run_started(event: RunStarted, console: Console) -> None:
    return


def _render_turn_started(event: TurnStarted, console: Console) -> None:
    return


def _render_model_started(event: ModelStarted, console: Console) -> None:
    console.print(
        "  [woven.accent]◌[/woven.accent] [woven.dim]Calling model…[/woven.dim]"
    )


def _render_model_completed(event: ModelCompleted, console: Console) -> None:
    console.print(
        "  [woven.success]✓[/woven.success] [woven.dim]Model responded[/woven.dim]"
    )


def _render_turn_completed(event: TurnCompleted, console: Console) -> None:
    console.print(
        Panel(
            Markdown(event.output_text),
            box=box.ROUNDED,
            title="[woven.success]woven[/woven.success]",
            title_align="left",
            border_style="woven.success",
        )
    )


def _render_run_completed(event: RunCompleted, console: Console) -> None:
    return


def _render_run_failed(event: RunFailed, console: Console) -> None:
    render_error(console, f"Turn failed: {event.error}")


def _render_unknown(event: Event, console: Console) -> None:
    console.print(f"  [woven.dim]· {type(event).__name__}[/woven.dim]")


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
