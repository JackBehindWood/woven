from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from woven.context import Context, ContextRequest, ContextSnapshot
from woven.events import (
    ApprovalDecided,
    ApprovalRequested,
    ContextRetrieved,
    Event,
    ModelCompleted,
    ModelStarted,
    ToolCallCompleted,
    ToolCallStarted,
)
from woven.models import Model, ModelRequest
from woven.permissions import ApprovalDenied, ApprovalPolicy
from woven.tools import Tool, ToolRequest

EventSink = Callable[[Event], None]


class WorkflowState(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    turn_id: str
    input_text: str
    model: Model
    tool: Tool | None = None
    context_source: Context | None = None
    context_request: ContextRequest | None = None
    context: ContextSnapshot | None = None
    approval: ApprovalPolicy | None = None
    output_text: str | None = None


def model_node(state: WorkflowState, emit: EventSink) -> WorkflowState:
    request = ModelRequest(
        purpose="chat_reply", input_text=state.input_text, context=state.context
    )
    emit(ModelStarted(turn_id=state.turn_id, request=request))
    response = state.model.generate(request)
    emit(ModelCompleted(turn_id=state.turn_id, response=response))
    return state.model_copy(update={"output_text": response.text})


def _build_tool_request(state: WorkflowState) -> ToolRequest:
    input_text = (
        state.output_text if state.output_text is not None else state.input_text
    )
    return ToolRequest(purpose="tool_call", input_text=input_text)


def tool_node(state: WorkflowState, emit: EventSink) -> WorkflowState:
    request = _build_tool_request(state)
    emit(ToolCallStarted(turn_id=state.turn_id, request=request))
    result = state.tool.execute(request)
    emit(ToolCallCompleted(turn_id=state.turn_id, result=result))
    return state.model_copy(update={"output_text": result.output_text})


def context_node(state: WorkflowState, emit: EventSink) -> WorkflowState:
    request = (
        state.context_request
        if state.context_request is not None
        else ContextRequest(purpose="context_retrieval")
    )
    snapshot = state.context_source.retrieve(request)
    emit(ContextRetrieved(turn_id=state.turn_id, snapshot=snapshot))
    return state.model_copy(update={"context": snapshot})


def approval_node(state: WorkflowState, emit: EventSink) -> WorkflowState:
    request = _build_tool_request(state)
    emit(ApprovalRequested(turn_id=state.turn_id, request=request))
    decision = state.approval.evaluate(request)
    emit(ApprovalDecided(turn_id=state.turn_id, decision=decision))
    if not decision.approved:
        raise ApprovalDenied(decision.reason or "approval denied")
    return state


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
