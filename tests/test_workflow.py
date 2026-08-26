from woven.events import Event
from woven.models import FakeModel
from woven.tools import MockTools
from woven.workflow import Workflow, WorkflowState, model_node, tool_node


def test_model_node_invokes_model_and_sets_output():
    events: list[Event] = []
    state = WorkflowState(
        turn_id="t1", input_text="hi", model=FakeModel(response_text="world")
    )

    result = model_node(state, events.append)

    assert result.output_text == "world"


def test_workflow_runs_steps_in_order():
    events: list[Event] = []
    workflow = Workflow(name="chat", steps=[model_node])
    state = WorkflowState(
        turn_id="t1", input_text="hi", model=FakeModel(response_text="world")
    )

    result = workflow.run(state, events.append)

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
