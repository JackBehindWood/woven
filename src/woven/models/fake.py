from __future__ import annotations

from woven.models.protocol import ModelError, ModelRequest, ModelResponse


class FakeModel:
    """Deterministic Model implementation. Permanent test infrastructure."""

    def __init__(self, response_text: str = "ok", *, raise_error: bool = False):
        self.received_requests: list[ModelRequest] = []
        self._response_text = response_text
        self._raise_error = raise_error

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.received_requests.append(request)
        if self._raise_error:
            raise ModelError("FakeModel configured to fail")
        return ModelResponse(text=self._response_text)
