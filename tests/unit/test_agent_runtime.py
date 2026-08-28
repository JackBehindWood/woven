import pytest

from woven.context import ContextError, ContextRequest, FilesystemContext
from woven.events import (
    ApprovalDecided,
    ApprovalRequested,
    ContextRetrieved,
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
from woven.models import FakeModel, ModelError
from woven.permissions import ApprovalDenied, AutoApprovalPolicy, MockApproval
from woven.runtime import AgentRun, AgentRuntime
from woven.tools import MockTools, ToolError


def test_run_turn_executes_and_returns_output():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = runtime.run_turn(run, "chat", "hi", FakeModel(response_text="hello"))

    assert turn.output_text == "hello"
    assert run.turns == [turn]


def test_run_turn_produces_expected_event_sequence():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = runtime.run_turn(run, "chat", "hi", FakeModel(response_text="hello"))

    assert [type(e) for e in turn.events] == [
        RunStarted,
        TurnStarted,
        ModelStarted,
        ModelCompleted,
        TurnCompleted,
        RunCompleted,
    ]
    assert turn.events == run.events


def test_model_node_receives_expected_request():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    model = FakeModel(response_text="hello")

    runtime.run_turn(run, "chat", "hello world", model)

    assert len(model.received_requests) == 1
    assert model.received_requests[0].input_text == "hello world"


def test_multiple_turns_can_use_different_modes_on_same_run():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    runtime.run_turn(run, "chat", "first", FakeModel(response_text="a"))
    runtime.run_turn(run, "chat", "second", FakeModel(response_text="b"))

    assert len(run.turns) == 2
    assert run.turns[0].output_text == "a"
    assert run.turns[1].output_text == "b"


def test_run_turn_failure_produces_failure_event_and_propagates():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    model = FakeModel(raise_error=True)

    with pytest.raises(ModelError):
        runtime.run_turn(run, "chat", "hi", model)

    assert [type(e) for e in run.events] == [
        RunStarted,
        TurnStarted,
        ModelStarted,
        RunFailed,
    ]


def test_run_turn_plan_mode_executes_context_and_model(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = runtime.run_turn(
        run,
        "plan",
        "hi",
        FakeModel(response_text="plan reply"),
        context_source=FilesystemContext(tmp_path),
        context_request=ContextRequest(purpose="p", paths=["a.txt"]),
    )

    assert turn.output_text == "plan reply"
    assert [type(e) for e in turn.events] == [
        RunStarted,
        TurnStarted,
        ContextRetrieved,
        ModelStarted,
        ModelCompleted,
        TurnCompleted,
        RunCompleted,
    ]


def test_run_turn_plan_mode_missing_context_path_produces_failure_event(tmp_path):
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    with pytest.raises(ContextError):
        runtime.run_turn(
            run,
            "plan",
            "hi",
            FakeModel(response_text="plan reply"),
            context_source=FilesystemContext(tmp_path),
            context_request=ContextRequest(purpose="p", paths=["missing.txt"]),
        )

    assert [type(e) for e in run.events] == [
        RunStarted,
        TurnStarted,
        RunFailed,
    ]


def test_run_turn_code_mode_executes_full_pipeline_when_approved(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    tool = MockTools(output_text="tool result")

    turn = runtime.run_turn(
        run,
        "code",
        "hi",
        FakeModel(response_text="model reply"),
        context_source=FilesystemContext(tmp_path),
        context_request=ContextRequest(purpose="p", paths=["a.txt"]),
        approval=MockApproval(approve=True),
        tool=tool,
    )

    assert turn.output_text == "tool result"
    assert [type(e) for e in turn.events] == [
        RunStarted,
        TurnStarted,
        ContextRetrieved,
        ModelStarted,
        ModelCompleted,
        ApprovalRequested,
        ApprovalDecided,
        ToolCallStarted,
        ToolCallCompleted,
        TurnCompleted,
        RunCompleted,
    ]


def test_run_turn_code_mode_denied_by_mock_approval_stops_before_tool(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    tool = MockTools(output_text="tool result")

    with pytest.raises(ApprovalDenied):
        runtime.run_turn(
            run,
            "code",
            "hi",
            FakeModel(response_text="model reply"),
            context_source=FilesystemContext(tmp_path),
            context_request=ContextRequest(purpose="p", paths=["a.txt"]),
            approval=MockApproval(approve=False),
            tool=tool,
        )

    assert [type(e) for e in run.events] == [
        RunStarted,
        TurnStarted,
        ContextRetrieved,
        ModelStarted,
        ModelCompleted,
        ApprovalRequested,
        ApprovalDecided,
        RunFailed,
    ]
    assert tool.received_requests == []


def test_run_turn_code_mode_denied_by_auto_approval_stops_before_tool(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    tool = MockTools(output_text="tool result")

    with pytest.raises(ApprovalDenied):
        runtime.run_turn(
            run,
            "code",
            "hi",
            FakeModel(response_text="please run rm -rf / now"),
            context_source=FilesystemContext(tmp_path),
            context_request=ContextRequest(purpose="p", paths=["a.txt"]),
            approval=AutoApprovalPolicy(),
            tool=tool,
        )

    assert tool.received_requests == []
    assert [type(e) for e in run.events][-1] is RunFailed


def test_run_turn_code_mode_tool_error_produces_failure_event(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    with pytest.raises(ToolError):
        runtime.run_turn(
            run,
            "code",
            "hi",
            FakeModel(response_text="model reply"),
            context_source=FilesystemContext(tmp_path),
            context_request=ContextRequest(purpose="p", paths=["a.txt"]),
            approval=MockApproval(approve=True),
            tool=MockTools(raise_error=True),
        )

    assert [type(e) for e in run.events][-1] is RunFailed
