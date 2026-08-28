import pytest

from woven.permissions import DEFAULT_DENY_PATTERNS, AutoApprovalPolicy
from woven.tools import ToolRequest


def test_auto_approval_approves_benign_request():
    policy = AutoApprovalPolicy()

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="list files"))

    assert decision.approved is True
    assert decision.reason is None


@pytest.mark.parametrize("pattern", DEFAULT_DENY_PATTERNS)
def test_auto_approval_denies_each_default_pattern(pattern):
    policy = AutoApprovalPolicy()

    decision = policy.evaluate(
        ToolRequest(purpose="p", input_text=f"please run {pattern} now")
    )

    assert decision.approved is False
    assert pattern in decision.reason


def test_auto_approval_matching_is_case_insensitive():
    policy = AutoApprovalPolicy()

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="SUDO reboot"))

    assert decision.approved is False


def test_auto_approval_custom_deny_patterns_override_defaults():
    policy = AutoApprovalPolicy(deny_patterns=("forbidden-word",))

    benign = policy.evaluate(ToolRequest(purpose="p", input_text="rm -rf /"))
    denied = policy.evaluate(
        ToolRequest(purpose="p", input_text="contains forbidden-word here")
    )

    assert benign.approved is True
    assert denied.approved is False
