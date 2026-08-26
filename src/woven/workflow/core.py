from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from woven.events import (
    Event,
    ModelCompleted,
    ModelStarted,
    ToolCallCompleted,
    ToolCallStarted,
)
from woven.models import Model, ModelRequest
from woven.tools import Tool, ToolRequest

EventSink = Callable[[Event], None]


class WorkflowState(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    turn_id: str
    input_text: str
    model: Model
    tool: Tool | None = None
    output_text: str | None = None


def model_node(state: WorkflowState, emit: EventSink) -> WorkflowState:
    request = ModelRequest(purpose="chat_reply", input_text=state.input_text)
    emit(ModelStarted(turn_id=state.turn_id, request=request))
    response = state.model.generate(request)
    emit(ModelCompleted(turn_id=state.turn_id, response=response))
    return state.model_copy(update={"output_text": response.text})


def tool_node(state: WorkflowState, emit: EventSink) -> WorkflowState:
    input_text = (
        state.output_text if state.output_text is not None else state.input_text
    )
    request = ToolRequest(purpose="tool_call", input_text=input_text)
    emit(ToolCallStarted(turn_id=state.turn_id, request=request))
    result = state.tool.execute(request)
    emit(ToolCallCompleted(turn_id=state.turn_id, result=result))
    return state.model_copy(update={"output_text": result.output_text})


class Workflow:
    def __init__(
        self,
        name: str,
        steps: list[Callable[[WorkflowState, EventSink], WorkflowState]],
    ):
        self.name = name
        self.steps = steps

    def run(self, state: WorkflowState, emit: EventSink) -> WorkflowState:
        for step in self.steps:
            state = step(state, emit)
        return state
