from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from woven.context import ContextSnapshot
from woven.models import ModelRequest, ModelResponse
from woven.permissions import ApprovalDecision
from woven.tools import ToolRequest, ToolResult


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn_id: str


class RunStarted(Event):
    run_id: str


class TurnStarted(Event):
    mode_name: str


class ModelStarted(Event):
    request: ModelRequest


class ModelCompleted(Event):
    response: ModelResponse


class ToolCallStarted(Event):
    request: ToolRequest


class ToolCallCompleted(Event):
    result: ToolResult


class ContextRetrieved(Event):
    snapshot: ContextSnapshot


class ApprovalRequested(Event):
    request: ToolRequest


class ApprovalDecided(Event):
    decision: ApprovalDecision


class TurnCompleted(Event):
    output_text: str


class RunCompleted(Event):
    run_id: str


class RunFailed(Event):
    run_id: str
    error: str
