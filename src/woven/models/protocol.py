from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ModelError(Exception):
    """Raised when a Model adapter fails to produce a response."""


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: str
    input_text: str


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str


@runtime_checkable
class Model(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...
