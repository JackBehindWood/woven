from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from woven.tools import ToolRequest


class ApprovalDenied(Exception):
    """Raised when a ToolRequest is denied by an ApprovalPolicy."""


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    reason: str | None = None


@runtime_checkable
class ApprovalPolicy(Protocol):
    def evaluate(self, request: ToolRequest) -> ApprovalDecision: ...
