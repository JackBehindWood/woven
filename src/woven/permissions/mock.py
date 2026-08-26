from __future__ import annotations

from woven.permissions.protocol import ApprovalDecision
from woven.tools import ToolRequest


class MockApproval:
    """Deterministic ApprovalPolicy. Permanent test infrastructure."""

    def __init__(self, *, approve: bool = True, reason: str | None = None):
        self.received_requests: list[ToolRequest] = []
        self._approve = approve
        self._reason = reason

    def evaluate(self, request: ToolRequest) -> ApprovalDecision:
        self.received_requests.append(request)
        return ApprovalDecision(approved=self._approve, reason=self._reason)
