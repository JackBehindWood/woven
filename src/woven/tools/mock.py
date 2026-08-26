from __future__ import annotations

from woven.tools.protocol import ToolError, ToolRequest, ToolResult


class MockTools:
    """Deterministic Tool implementation. Permanent test infrastructure."""

    def __init__(self, output_text: str = "ok", *, raise_error: bool = False):
        self.received_requests: list[ToolRequest] = []
        self._output_text = output_text
        self._raise_error = raise_error

    def execute(self, request: ToolRequest) -> ToolResult:
        self.received_requests.append(request)
        if self._raise_error:
            raise ToolError("MockTools configured to fail")
        return ToolResult(output_text=self._output_text)
