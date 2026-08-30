import io

from rich.console import Console

from woven.client.cli.console import make_console
from woven.client.cli.render import (
    render_banner,
    render_diagnostics,
    render_event,
    render_header,
    render_hint,
    render_status_panel,
)
from woven.context import ContextFile, ContextSnapshot
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
from woven.models import ModelRequest, ModelResponse
from woven.permissions import ApprovalDecision
from woven.tools import ToolRequest, ToolResult


def _capturing_console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return make_console(file=buffer, width=100, no_color=True), buffer


def test_render_banner_prints_wordmark():
    console, buffer = _capturing_console()

    render_banner(console)

    assert "W O V E N" in buffer.getvalue()


def test_render_hint_prints_exit_instructions():
    console, buffer = _capturing_console()

    render_hint(console)

    output = buffer.getvalue()
    assert "exit" in output
    assert "quit" in output
    assert ":q" in output


def test_turn_completed_renders_output_text():
    console, buffer = _capturing_console()

    render_event(TurnCompleted(turn_id="t1", output_text="hello world"), console)

    assert "hello world" in buffer.getvalue()


def test_run_failed_renders_error_message():
    console, buffer = _capturing_console()

    render_event(RunFailed(turn_id="t1", run_id="r1", error="boom"), console)

    output = buffer.getvalue()
    assert "Turn failed" in output
    assert "boom" in output


def test_model_started_and_completed_are_suppressed():
    console, buffer = _capturing_console()

    render_event(
        ModelStarted(
            turn_id="t1", request=ModelRequest(purpose="chat_reply", input_text="hi")
        ),
        console,
    )
    render_event(
        ModelCompleted(turn_id="t1", response=ModelResponse(text="hello")), console
    )

    assert buffer.getvalue() == ""


def test_run_started_turn_started_run_completed_are_suppressed():
    console, buffer = _capturing_console()

    render_event(RunStarted(turn_id="t1", run_id="r1"), console)
    render_event(TurnStarted(turn_id="t1", mode_name="chat"), console)
    render_event(RunCompleted(turn_id="t1", run_id="r1"), console)

    assert buffer.getvalue() == ""


def test_unknown_event_type_falls_back_without_crashing():
    class _FutureEvent(Event):
        pass

    console, buffer = _capturing_console()

    render_event(_FutureEvent(turn_id="t1"), console)

    assert "_FutureEvent" in buffer.getvalue()


def test_tool_call_started_renders_input_text():
    console, buffer = _capturing_console()

    render_event(
        ToolCallStarted(
            turn_id="t1", request=ToolRequest(purpose="tool_call", input_text="do it")
        ),
        console,
    )

    assert "do it" in buffer.getvalue()


def test_tool_call_completed_renders_output_text():
    console, buffer = _capturing_console()

    render_event(
        ToolCallCompleted(turn_id="t1", result=ToolResult(output_text="done")),
        console,
    )

    assert "done" in buffer.getvalue()


def test_context_retrieved_renders_file_paths():
    console, buffer = _capturing_console()

    render_event(
        ContextRetrieved(
            turn_id="t1",
            snapshot=ContextSnapshot(files=[ContextFile(path="a.py", content="x")]),
        ),
        console,
    )

    assert "a.py" in buffer.getvalue()


def test_context_retrieved_renders_no_files_matched_when_empty():
    console, buffer = _capturing_console()

    render_event(
        ContextRetrieved(turn_id="t1", snapshot=ContextSnapshot(files=[])),
        console,
    )

    assert "no files matched" in buffer.getvalue()


def test_approval_requested_is_suppressed():
    console, buffer = _capturing_console()

    render_event(
        ApprovalRequested(
            turn_id="t1", request=ToolRequest(purpose="tool_call", input_text="x")
        ),
        console,
    )

    assert buffer.getvalue() == ""


def test_approval_decided_approved_renders_approved_line():
    console, buffer = _capturing_console()

    render_event(
        ApprovalDecided(turn_id="t1", decision=ApprovalDecision(approved=True)),
        console,
    )

    assert "approved" in buffer.getvalue()


def test_approval_decided_denied_renders_reason():
    console, buffer = _capturing_console()

    render_event(
        ApprovalDecided(
            turn_id="t1",
            decision=ApprovalDecision(approved=False, reason="too risky"),
        ),
        console,
    )

    output = buffer.getvalue()
    assert "denied" in output
    assert "too risky" in output


def test_render_header_default_mode_has_no_tool_disclosure():
    console, buffer = _capturing_console()

    render_header(console, response_text="hi")

    assert "MockTools" not in buffer.getvalue()


def test_render_header_code_mode_discloses_mock_tools():
    console, buffer = _capturing_console()

    render_header(console, response_text="hi", mode_name="code")

    output = buffer.getvalue()
    assert "MockTools" in output
    assert "code" in output


def test_render_status_panel_prints_title_and_lines():
    console, buffer = _capturing_console()

    render_status_panel(console, "status", ["line one", "line two"])

    output = buffer.getvalue()
    assert "status" in output
    assert "line one" in output
    assert "line two" in output


def test_render_diagnostics_only_failures_hides_ok_but_keeps_summary():
    console, buffer = _capturing_console()
    checks = [
        DiagnosticCheck(name="environment", status=CheckStatus.OK, message="fine"),
        DiagnosticCheck(name="dependencies", status=CheckStatus.OK, message="fine"),
    ]

    render_diagnostics(console, checks, only_failures=True)

    output = buffer.getvalue()
    assert "environment" not in output
    assert "dependencies" not in output
    assert "2 ok, 0 warn, 0 fail" in output


def test_render_diagnostics_only_failures_keeps_warn_and_fail_lines():
    console, buffer = _capturing_console()
    checks = [
        DiagnosticCheck(name="environment", status=CheckStatus.OK, message="fine"),
        DiagnosticCheck(
            name="config:mode", status=CheckStatus.WARN, message="stale mode"
        ),
        DiagnosticCheck(
            name="provider", status=CheckStatus.FAIL, message="unreachable"
        ),
    ]

    render_diagnostics(console, checks, only_failures=True)

    output = buffer.getvalue()
    assert "environment" not in output
    assert "config:mode" in output
    assert "provider" in output
    assert "1 ok, 1 warn, 1 fail" in output
