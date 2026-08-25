from woven.events import Event
from woven.models import FakeModel
from woven.workflow import Workflow, WorkflowState, model_node


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
