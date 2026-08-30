from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from woven.context import Context, ContextError, ContextRequest
from woven.events import (
    Event,
    RunCompleted,
    RunFailed,
    RunStarted,
    TurnCompleted,
    TurnStarted,
)
from woven.models import Model, ModelError
from woven.modes import BUILTIN_MODES
from woven.permissions import ApprovalDenied, ApprovalPolicy
from woven.tools import Tool, ToolError
from woven.workflow import WorkflowError, WorkflowState


class Turn(BaseModel):
    turn_id: str
    mode_name: str
    input_text: str
    output_text: str | None = None
    events: list[Event] = Field(default_factory=list)


class AgentRun(BaseModel):
    run_id: str
    turns: list[Turn] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)


class AgentRuntime:
    def run_turn(
        self,
        run: AgentRun,
        mode_name: str,
        input_text: str,
        model: Model,
        *,
        tool: Tool | None = None,
        context_source: Context | None = None,
        context_request: ContextRequest | None = None,
        approval: ApprovalPolicy | None = None,
    ) -> Turn:
        turn = Turn(
            turn_id=uuid.uuid4().hex, mode_name=mode_name, input_text=input_text
        )

        def emit(event: Event) -> None:
            turn.events.append(event)
            run.events.append(event)

        emit(RunStarted(turn_id=turn.turn_id, run_id=run.run_id))
        emit(TurnStarted(turn_id=turn.turn_id, mode_name=mode_name))

        mode = BUILTIN_MODES[mode_name]
        workflow = mode.workflow_factory()
        state = WorkflowState(
            turn_id=turn.turn_id,
            input_text=input_text,
            model=model,
            tool=tool,
            context_source=context_source,
            context_request=context_request,
            approval=approval,
        )

        try:
            state = workflow.run(state, emit)
        except (
            ModelError,
            ToolError,
            ContextError,
            ApprovalDenied,
            WorkflowError,
        ) as exc:
            emit(RunFailed(turn_id=turn.turn_id, run_id=run.run_id, error=str(exc)))
            raise

        turn.output_text = state.output_text
        emit(TurnCompleted(turn_id=turn.turn_id, output_text=state.output_text))
        run.turns.append(turn)
        emit(RunCompleted(turn_id=turn.turn_id, run_id=run.run_id))
        return turn
