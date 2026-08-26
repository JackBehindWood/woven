from woven.permissions import MockApproval
from woven.tools import ToolRequest


def test_mock_approval_default_approves():
    policy = MockApproval()

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="do it"))

    assert decision.approved is True
    assert decision.reason is None


def test_mock_approval_configured_denial_returns_reason():
    policy = MockApproval(approve=False, reason="not allowed")

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="do it"))

    assert decision.approved is False
    assert decision.reason == "not allowed"


def test_mock_approval_records_received_requests():
    policy = MockApproval()
    request = ToolRequest(purpose="p", input_text="do it")

    policy.evaluate(request)

    assert policy.received_requests == [request]
