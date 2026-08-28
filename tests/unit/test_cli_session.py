import io
from unittest.mock import MagicMock

from rich.console import Console

from woven.client.cli.console import make_console
from woven.client.cli.session import run_chat_turn
from woven.context import ContextRequest, FilesystemContext
from woven.models import FakeModel
from woven.permissions import MockApproval
from woven.runtime import AgentRun, AgentRuntime
from woven.tools import MockTools


def _capturing_console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return make_console(file=buffer, width=100, no_color=True), buffer


def test_run_chat_turn_shows_status_spinner_around_model_call():
    console, _ = _capturing_console()
    console.status = MagicMock(wraps=console.status)
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    run_chat_turn(runtime, run, "chat", "hi", FakeModel(response_text="hello"), console)

    console.status.assert_called_once()
    assert "Calling model" in console.status.call_args[0][0]


def test_run_chat_turn_success_renders_response_and_returns_turn():
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = run_chat_turn(
        runtime, run, "chat", "hi", FakeModel(response_text="hello"), console
    )

    assert turn is not None
    assert turn.output_text == "hello"
    assert "hello" in buffer.getvalue()
    assert run.turns == [turn]


def test_run_chat_turn_model_error_renders_failure_and_returns_none():
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    result = run_chat_turn(
        runtime, run, "chat", "hi", FakeModel(raise_error=True), console
    )

    assert result is None
    assert "Turn failed" in buffer.getvalue()
    assert run.turns == []


def test_run_chat_turn_unknown_mode_renders_error_and_returns_none():
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    result = run_chat_turn(
        runtime,
        run,
        "not-a-real-mode",
        "hi",
        FakeModel(response_text="x"),
        console,
    )

    assert result is None
    assert "Unknown mode" in buffer.getvalue()


def test_run_chat_turn_plan_mode_retrieves_real_context(tmp_path):
    (tmp_path / "notes.py").write_text("print('hi')")
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = run_chat_turn(
        runtime,
        run,
        "plan",
        "hi",
        FakeModel(response_text="hello"),
        console,
        context_source=FilesystemContext(root=tmp_path),
        context_request=ContextRequest(purpose="context_retrieval", name_glob="*.py"),
    )

    assert turn is not None
    assert "notes.py" in buffer.getvalue()


def test_run_chat_turn_code_mode_runs_tool_with_approval(tmp_path):
    console, _ = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    tool = MockTools(output_text="tool ran")

    turn = run_chat_turn(
        runtime,
        run,
        "code",
        "hi",
        FakeModel(response_text="hello"),
        console,
        tool=tool,
        context_source=FilesystemContext(root=tmp_path),
        approval=MockApproval(approve=True),
    )

    assert turn is not None
    assert turn.output_text == "tool ran"


def test_run_chat_turn_tool_error_renders_failure_and_returns_none(tmp_path):
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    result = run_chat_turn(
        runtime,
        run,
        "code",
        "hi",
        FakeModel(response_text="hello"),
        console,
        tool=MockTools(raise_error=True),
        context_source=FilesystemContext(root=tmp_path),
        approval=MockApproval(approve=True),
    )

    assert result is None
    assert "Turn failed" in buffer.getvalue()
    assert run.turns == []


def test_run_chat_turn_context_error_renders_failure_and_returns_none(tmp_path):
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    result = run_chat_turn(
        runtime,
        run,
        "plan",
        "hi",
        FakeModel(response_text="hello"),
        console,
        context_source=FilesystemContext(root=tmp_path),
        context_request=ContextRequest(
            purpose="context_retrieval", paths=["missing.txt"]
        ),
    )

    assert result is None
    assert "Turn failed" in buffer.getvalue()
    assert run.turns == []


def test_run_chat_turn_approval_denied_renders_failure_and_returns_none(tmp_path):
    console, buffer = _capturing_console()
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    result = run_chat_turn(
        runtime,
        run,
        "code",
        "hi",
        FakeModel(response_text="hello"),
        console,
        tool=MockTools(),
        context_source=FilesystemContext(root=tmp_path),
        approval=MockApproval(approve=False, reason="nope"),
    )

    assert result is None
    assert "Turn failed" in buffer.getvalue()
    assert run.turns == []
