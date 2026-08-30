from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from woven import __version__
from woven.diagnostics import CheckStatus, DiagnosticCheck
from woven.events import (
    ApprovalDecided,
    ApprovalRequested,
    ContextRetrieved,
    Event,
    ModelCompleted,
    ModelStarted,
    RunCompleted,
    RunFailed,
    RunStarted,
    ToolCallCompleted,
    ToolCallStarted,
    TurnCompleted,
    TurnStarted,
)

_TRUNCATE_LEN = 80


def _truncate(text: str, limit: int = _TRUNCATE_LEN) -> str:
    text = text.replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def render_banner(console: Console) -> None:
    console.print("[woven.accent]W O V E N[/woven.accent]", justify="center")


def render_header(
    console: Console,
    *,
    response_text: str,
    mode_name: str = "chat",
    model_description: str | None = None,
) -> None:
    workspace_line = (
        f"[woven.dim]workspace:[/woven.dim] {Path.cwd()}  "
        f"[woven.dim](current directory — Woven has no project/workspace "
        f"concept yet)[/woven.dim]"
    )
    if model_description is not None:
        model_line = f"[woven.accent]model:[/woven.accent] {model_description}"
    else:
        model_line = (
            f"[woven.warning]demo model:[/woven.warning] FakeModel — every "
            f'message gets this same fixed reply: "{response_text}"'
        )
    lines = [
        f"[woven.accent]Woven[/woven.accent] [woven.dim]v{__version__}[/woven.dim]",
        workspace_line,
        model_line,
    ]
    if mode_name == "code":
        lines.append(
            "[woven.warning]demo tool:[/woven.warning] MockTools — tool calls "
            'always return a fixed result ("ok")'
        )
    console.print(
        Panel(
            "\n".join(lines),
            box=box.ROUNDED,
            border_style="woven.accent",
            title=f"woven {mode_name}",
            title_align="left",
        )
    )


def render_status_panel(console: Console, title: str, lines: Iterable[str]) -> None:
    console.print(
        Panel(
            "\n".join(lines),
            box=box.ROUNDED,
            border_style="woven.accent",
            title=title,
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


_CHECK_STATUS_STYLE: dict[CheckStatus, tuple[str, str]] = {
    CheckStatus.OK: ("woven.success", "✓"),
    CheckStatus.WARN: ("woven.warning", "!"),
    CheckStatus.FAIL: ("woven.error", "✗"),
}


def render_diagnostics(
    console: Console,
    checks: Iterable[DiagnosticCheck],
    *,
    only_failures: bool = False,
) -> None:
    checks = list(checks)
    lines: list[str] = []
    counts = {CheckStatus.OK: 0, CheckStatus.WARN: 0, CheckStatus.FAIL: 0}
    for check in checks:
        counts[check.status] += 1
        if only_failures and check.status == CheckStatus.OK:
            continue
        style, symbol = _CHECK_STATUS_STYLE[check.status]
        lines.append(f"[{style}]{symbol} {check.name}[/{style}]: {check.message}")
        if check.fix_hint:
            lines.append(f"  [woven.dim]fix:[/woven.dim] {check.fix_hint}")

    lines.append("")
    lines.append(
        f"{counts[CheckStatus.OK]} ok, {counts[CheckStatus.WARN]} warn, "
        f"{counts[CheckStatus.FAIL]} fail"
    )
    render_status_panel(console, "doctor", lines)


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
    return


def _render_model_completed(event: ModelCompleted, console: Console) -> None:
    return


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


def _render_tool_call_started(event: ToolCallStarted, console: Console) -> None:
    console.print(
        f"  [woven.dim]→ tool call:[/woven.dim] {_truncate(event.request.input_text)}"
    )


def _render_tool_call_completed(event: ToolCallCompleted, console: Console) -> None:
    console.print(
        f"  [woven.dim]← tool result:[/woven.dim] {_truncate(event.result.output_text)}"
    )


def _render_context_retrieved(event: ContextRetrieved, console: Console) -> None:
    files = event.snapshot.files
    if not files:
        body = "[woven.dim]no files matched[/woven.dim]"
    else:
        body = "\n".join(f"[woven.dim]·[/woven.dim] {f.path}" for f in files)
    console.print(
        Panel(
            body,
            box=box.ROUNDED,
            border_style="woven.dim",
            title=f"context ({len(files)} file{'s' if len(files) != 1 else ''})",
            title_align="left",
        )
    )


def _render_approval_requested(event: ApprovalRequested, console: Console) -> None:
    return


def _render_approval_decided(event: ApprovalDecided, console: Console) -> None:
    if event.decision.approved:
        console.print("  [woven.success]✓ approved[/woven.success]")
    else:
        reason = event.decision.reason or "denied"
        console.print(f"  [woven.warning]✗ denied: {reason}[/woven.warning]")


def _render_unknown(event: Event, console: Console) -> None:
    console.print(f"  [woven.dim]· {type(event).__name__}[/woven.dim]")


_RENDERERS: dict[type[Event], Callable[[Event, Console], None]] = {
    RunStarted: _render_run_started,
    TurnStarted: _render_turn_started,
    ModelStarted: _render_model_started,
    ModelCompleted: _render_model_completed,
    ToolCallStarted: _render_tool_call_started,
    ToolCallCompleted: _render_tool_call_completed,
    ContextRetrieved: _render_context_retrieved,
    ApprovalRequested: _render_approval_requested,
    ApprovalDecided: _render_approval_decided,
    TurnCompleted: _render_turn_completed,
    RunCompleted: _render_run_completed,
    RunFailed: _render_run_failed,
}


def render_event(event: Event, console: Console) -> None:
    _RENDERERS.get(type(event), _render_unknown)(event, console)
