from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ToolError(Exception):
    """Raised when a Tool implementation fails to produce a result."""


class ToolRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: str
    input_text: str


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    output_text: str


@runtime_checkable
class Tool(Protocol):
    def execute(self, request: ToolRequest) -> ToolResult: ...
