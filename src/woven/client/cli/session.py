from __future__ import annotations

from rich.console import Console

from woven.client.cli.render import render_error, render_event
from woven.context import Context, ContextError, ContextRequest
from woven.models import Model, ModelError
from woven.permissions import ApprovalDenied, ApprovalPolicy
from woven.runtime import AgentRun, AgentRuntime, Turn
from woven.tools import Tool, ToolError


def run_chat_turn(
    runtime: AgentRuntime,
    run: AgentRun,
    mode_name: str,
    input_text: str,
    model: Model,
    console: Console,
    *,
    tool: Tool | None = None,
    context_source: Context | None = None,
    context_request: ContextRequest | None = None,
    approval: ApprovalPolicy | None = None,
) -> Turn | None:
    """Run one turn and render its recorded events.

    Returns the completed Turn, or None if the turn failed (a rendered
    error has already been printed to `console` in that case).
    """
    try:
        with console.status("Calling model…", spinner="dots"):
            turn = runtime.run_turn(
                run,
                mode_name,
                input_text,
                model,
                tool=tool,
                context_source=context_source,
                context_request=context_request,
                approval=approval,
            )
    except (ModelError, ToolError, ContextError, ApprovalDenied):
        render_event(run.events[-1], console)
        return None
    except KeyError as exc:
        render_error(console, f"Unknown mode: {exc}")
        return None

    for event in turn.events:
        render_event(event, console)
    return turn
