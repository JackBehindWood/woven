from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from woven.workflow import Workflow, model_node


class Mode(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    workflow_factory: Callable[[], Workflow]


def build_chat_workflow() -> Workflow:
    return Workflow(name="chat", steps=[model_node])


BUILTIN_MODES: dict[str, Mode] = {
    "chat": Mode(name="chat", workflow_factory=build_chat_workflow),
}
