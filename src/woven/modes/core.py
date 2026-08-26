from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from woven.workflow import Workflow, approval_node, context_node, model_node, tool_node


class Mode(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    workflow_factory: Callable[[], Workflow]


def build_chat_workflow() -> Workflow:
    return Workflow(name="chat", steps=[model_node])


def build_plan_workflow() -> Workflow:
    return Workflow(name="plan", steps=[context_node, model_node])


def build_code_workflow() -> Workflow:
    return Workflow(
        name="code", steps=[context_node, model_node, approval_node, tool_node]
    )


BUILTIN_MODES: dict[str, Mode] = {
    "chat": Mode(name="chat", workflow_factory=build_chat_workflow),
    "plan": Mode(name="plan", workflow_factory=build_plan_workflow),
    "code": Mode(name="code", workflow_factory=build_code_workflow),
}
