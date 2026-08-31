from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class SandboxError(Exception):
    """Raised when a Sandbox implementation cannot execute a command at all."""


class SandboxRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    command: Sequence[str]
    cwd: str | None = None
    timeout: float | None = None


class SandboxResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


@runtime_checkable
class Sandbox(Protocol):
    def run(self, request: SandboxRequest) -> SandboxResult: ...
