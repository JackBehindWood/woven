from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Provider(Protocol):
    provider_name: str
    model_id: str

    def check_connection(self) -> None: ...
