import pytest

from woven.context import ContextRequest, FilesystemContext
from woven.events import Event
from woven.models import FakeModel
from woven.permissions import ApprovalDenied, MockApproval
from woven.tools import MockTools
from woven.workflow import (
    Workflow,
    WorkflowError,
    WorkflowState,
    approval_node,
    context_node,
    model_node,
    tool_node,
)


def test_model_node_invokes_model_and_sets_output():
    events: list[Event] = []
    state = WorkflowState(
        turn_id="t1", input_text="hi", model=FakeModel(response_text="world")
    )

    result = model_node(state, events.append)

    assert result.output_text == "world"


def test_tool_node_invokes_tool_and_sets_output():
    events: list[Event] = []
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(),
        tool=MockTools(output_text="tool result"),
    )

    result = tool_node(state, events.append)

    assert result.output_text == "tool result"


def test_workflow_mixes_model_and_tool_steps():
    events: list[Event] = []
    tool = MockTools(output_text="tool result")
    workflow = Workflow(name="mixed", steps=[model_node, tool_node])
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(response_text="model reply"),
        tool=tool,
    )

    result = workflow.run(state, events.append)

    assert result.output_text == "tool result"
    assert tool.received_requests[0].input_text == "model reply"


def test_context_node_invokes_context_and_sets_snapshot(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    events: list[Event] = []
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(),
        context_source=FilesystemContext(tmp_path),
        context_request=ContextRequest(purpose="p", paths=["a.txt"]),
    )

    result = context_node(state, events.append)

    assert result.context is not None
    assert result.context.files[0].content == "file contents"


def test_workflow_chains_context_into_model_request(tmp_path):
    (tmp_path / "a.txt").write_text("file contents")
    events: list[Event] = []
    model = FakeModel(response_text="reply")
    workflow = Workflow(name="ctx", steps=[context_node, model_node])
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=model,
        context_source=FilesystemContext(tmp_path),
        context_request=ContextRequest(purpose="p", paths=["a.txt"]),
    )

    workflow.run(state, events.append)

    assert model.received_requests[0].context is not None
    assert model.received_requests[0].context.files[0].content == "file contents"


def test_approval_node_approves_and_leaves_state_unchanged():
    events: list[Event] = []
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(),
        approval=MockApproval(approve=True),
    )

    result = approval_node(state, events.append)

    assert result == state


def test_approval_node_denies_raises_approval_denied():
    events: list[Event] = []
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(),
        approval=MockApproval(approve=False, reason="no"),
    )

    with pytest.raises(ApprovalDenied):
        approval_node(state, events.append)


def test_workflow_runs_approval_then_tool_when_approved():
    events: list[Event] = []
    tool = MockTools(output_text="tool result")
    workflow = Workflow(name="gated", steps=[model_node, approval_node, tool_node])
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(response_text="model reply"),
        approval=MockApproval(approve=True),
        tool=tool,
    )

    result = workflow.run(state, events.append)

    assert result.output_text == "tool result"
    assert tool.received_requests


def test_workflow_stops_before_tool_when_approval_denied():
    events: list[Event] = []
    tool = MockTools(output_text="tool result")
    workflow = Workflow(name="gated", steps=[model_node, approval_node, tool_node])
    state = WorkflowState(
        turn_id="t1",
        input_text="hi",
        model=FakeModel(response_text="model reply"),
        approval=MockApproval(approve=False),
        tool=tool,
    )

    with pytest.raises(ApprovalDenied):
        workflow.run(state, events.append)

    assert tool.received_requests == []


def test_tool_node_missing_tool_raises_workflow_error():
    events: list[Event] = []
    state = WorkflowState(turn_id="t1", input_text="hi", model=FakeModel())

    with pytest.raises(WorkflowError):
        tool_node(state, events.append)


def test_context_node_missing_context_source_raises_workflow_error():
    events: list[Event] = []
    state = WorkflowState(turn_id="t1", input_text="hi", model=FakeModel())

    with pytest.raises(WorkflowError):
        context_node(state, events.append)


def test_approval_node_missing_approval_raises_workflow_error():
    events: list[Event] = []
    state = WorkflowState(turn_id="t1", input_text="hi", model=FakeModel())

    with pytest.raises(WorkflowError):
        approval_node(state, events.append)
