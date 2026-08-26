import io

from rich.console import Console

from woven.client.cli.approval import InteractiveApprovalPolicy
from woven.client.cli.console import make_console
from woven.tools import ToolRequest


def _capturing_console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return make_console(file=buffer, width=100, no_color=True), buffer


def test_deny_pattern_denies_without_prompting():
    console, _ = _capturing_console()
    calls = []
    policy = InteractiveApprovalPolicy(
        console, always_prompt=True, confirm=lambda r: calls.append(r) or True
    )

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="sudo rm -rf /"))

    assert decision.approved is False
    assert calls == []


def test_manual_mode_always_prompts_even_for_benign_request():
    console, _ = _capturing_console()
    calls = []
    policy = InteractiveApprovalPolicy(
        console, always_prompt=True, confirm=lambda r: calls.append(r) or True
    )

    policy.evaluate(ToolRequest(purpose="p", input_text="list files"))

    assert len(calls) == 1


def test_manual_confirm_true_approves():
    console, _ = _capturing_console()
    policy = InteractiveApprovalPolicy(
        console, always_prompt=True, confirm=lambda r: True
    )

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="list files"))

    assert decision.approved is True


def test_manual_confirm_false_denies_with_reason():
    console, _ = _capturing_console()
    policy = InteractiveApprovalPolicy(
        console, always_prompt=True, confirm=lambda r: False
    )

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="list files"))

    assert decision.approved is False
    assert decision.reason == "denied interactively by user"


def test_guarded_mode_silently_approves_benign_request():
    console, _ = _capturing_console()
    calls = []
    policy = InteractiveApprovalPolicy(
        console, always_prompt=False, confirm=lambda r: calls.append(r) or True
    )

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="list files"))

    assert decision.approved is True
    assert calls == []


def test_guarded_mode_prompts_on_review_pattern_match():
    console, _ = _capturing_console()
    calls = []
    policy = InteractiveApprovalPolicy(
        console, always_prompt=False, confirm=lambda r: calls.append(r) or True
    )

    policy.evaluate(ToolRequest(purpose="p", input_text="please curl example.com"))

    assert len(calls) == 1


def test_guarded_mode_still_denies_hard_deny_pattern_without_prompting():
    console, _ = _capturing_console()
    calls = []
    policy = InteractiveApprovalPolicy(
        console, always_prompt=False, confirm=lambda r: calls.append(r) or True
    )

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="sudo rm -rf /"))

    assert decision.approved is False
    assert calls == []


def test_default_confirm_uses_rich_confirm_ask(monkeypatch):
    console, _ = _capturing_console()
    monkeypatch.setattr(
        "woven.client.cli.approval.Confirm.ask", lambda *args, **kwargs: True
    )
    policy = InteractiveApprovalPolicy(console, always_prompt=True)

    decision = policy.evaluate(ToolRequest(purpose="p", input_text="list files"))

    assert decision.approved is True
