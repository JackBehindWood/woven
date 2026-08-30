from woven.permissions.auto import DEFAULT_DENY_PATTERNS, AutoApprovalPolicy
from woven.permissions.mock import MockApproval
from woven.permissions.protocol import ApprovalDecision, ApprovalDenied, ApprovalPolicy

PERMISSION_MODES: tuple[str, ...] = ("auto", "guarded", "manual")

__all__ = [
    "DEFAULT_DENY_PATTERNS",
    "PERMISSION_MODES",
    "ApprovalDecision",
    "ApprovalDenied",
    "ApprovalPolicy",
    "AutoApprovalPolicy",
    "MockApproval",
]
