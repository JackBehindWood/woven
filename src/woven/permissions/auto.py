from __future__ import annotations

from woven.permissions.protocol import ApprovalDecision
from woven.tools import ToolRequest

DEFAULT_DENY_PATTERNS: tuple[str, ...] = (
    "rm -rf",
    "sudo ",
    "drop table",
    "drop database",
    "chmod -r 777",
    "mkfs.",
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
    ":(){ :|:& };:",
)


class AutoApprovalPolicy:
    """Deterministic ApprovalPolicy: approves by default, denies suspected-harmful requests.

    No interactive human-approval mechanism exists in this runtime yet, so a
    request matching a deny pattern is denied outright rather than left pending.
    """

    def __init__(self, deny_patterns: tuple[str, ...] = DEFAULT_DENY_PATTERNS):
        self._deny_patterns = deny_patterns

    def evaluate(self, request: ToolRequest) -> ApprovalDecision:
        input_text_lower = request.input_text.lower()
        for pattern in self._deny_patterns:
            if pattern.lower() in input_text_lower:
                return ApprovalDecision(
                    approved=False, reason=f"blocked: matched pattern {pattern!r}"
                )
        return ApprovalDecision(approved=True)
