from __future__ import annotations

from rich.console import Console

from woven.client.cli.render import render_error, render_event
from woven.models import Model, ModelError
from woven.runtime import AgentRun, AgentRuntime, Turn


def run_chat_turn(
    runtime: AgentRuntime,
    run: AgentRun,
    mode_name: str,
    input_text: str,
    model: Model,
    console: Console,
) -> Turn | None:
    """Run one turn and render its recorded events.

    Returns the completed Turn, or None if the turn failed (a rendered
    error has already been printed to `console` in that case).
    """
    try:
        turn = runtime.run_turn(run, mode_name, input_text, model)
    except ModelError:
        render_event(run.events[-1], console)
        return None
    except KeyError as exc:
        render_error(console, f"Unknown mode: {exc}")
        return None

    for event in turn.events:
        render_event(event, console)
    return turn
