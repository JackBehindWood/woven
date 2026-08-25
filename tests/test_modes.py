from woven.modes import BUILTIN_MODES
from woven.workflow import model_node


def test_chat_mode_builds_workflow_with_model_node():
    workflow = BUILTIN_MODES["chat"].workflow_factory()

    assert workflow.steps == [model_node]
