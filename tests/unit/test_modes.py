from woven.modes import BUILTIN_MODES
from woven.workflow import approval_node, context_node, model_node, tool_node


def test_chat_mode_builds_workflow_with_model_node():
    workflow = BUILTIN_MODES["chat"].workflow_factory()

    assert workflow.steps == [model_node]


def test_plan_mode_builds_workflow_with_context_and_model_nodes():
    workflow = BUILTIN_MODES["plan"].workflow_factory()

    assert workflow.steps == [context_node, model_node]


def test_code_mode_builds_workflow_with_full_pipeline():
    workflow = BUILTIN_MODES["code"].workflow_factory()

    assert workflow.steps == [context_node, model_node, approval_node, tool_node]
