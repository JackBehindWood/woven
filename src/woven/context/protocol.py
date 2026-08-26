from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ContextError(Exception):
    """Raised when a Context implementation fails to produce a snapshot."""


class ContextFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    content: str


class ContextRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: str
    paths: list[str] = Field(default_factory=list)
    name_glob: str | None = None
    text_query: str | None = None


class ContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    files: list[ContextFile] = Field(default_factory=list)


@runtime_checkable
class Context(Protocol):
    def retrieve(self, request: ContextRequest) -> ContextSnapshot: ...
