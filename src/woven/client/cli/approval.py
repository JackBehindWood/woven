from __future__ import annotations

from collections.abc import Callable

from rich.console import Console
from rich.prompt import Confirm

from woven.permissions import ApprovalDecision, AutoApprovalPolicy
from woven.tools import ToolRequest

ConfirmFn = Callable[[ToolRequest], bool]

# Deliberately a different, broader/softer list than AutoApprovalPolicy's
# DEFAULT_DENY_PATTERNS — if "guarded" reused the deny list as its review
# trigger, the review step would never fire (anything matching the deny
# list is already hard-denied by the composed deny_check first). This list
# catches "worth a second look" actions that aren't already hard-denied.
DEFAULT_REVIEW_PATTERNS: tuple[str, ...] = (
    "rm ",
    "sudo",
    "git push --force",
    "delete",
    "drop ",
    "chmod",
    "curl",
    "wget",
    "mv /",
)


class InteractiveApprovalPolicy:
    """CLI-only ApprovalPolicy backing the "guarded" and "manual" tiers.

    Both share one mechanism: a hard-deny floor (composed AutoApprovalPolicy),
    then either a silent approval or an interactive Rich prompt.
    - "manual" (always_prompt=True): every request past the deny floor is
      prompted, unconditionally — never a silent approval.
    - "guarded" (always_prompt=False): prompted only if it matches
      review_patterns; otherwise silently approved.

    CLI-specific I/O, so this lives under woven.client.cli, not
    woven.permissions (runtime-agnostic, must stay Rich/Typer-free) or
    woven.workflow (depends only on the ApprovalPolicy protocol).
    """

    def __init__(
        self,
        console: Console,
        *,
        deny_check: AutoApprovalPolicy | None = None,
        review_patterns: tuple[str, ...] | None = DEFAULT_REVIEW_PATTERNS,
        always_prompt: bool = True,
        confirm: ConfirmFn | None = None,
    ) -> None:
        self._console = console
        self._deny_check = (
            deny_check if deny_check is not None else AutoApprovalPolicy()
        )
        self._review_patterns = review_patterns
        self._always_prompt = always_prompt
        self._confirm = confirm if confirm is not None else self._prompt

    def evaluate(self, request: ToolRequest) -> ApprovalDecision:
        deny_decision = self._deny_check.evaluate(request)
        if not deny_decision.approved:
            return deny_decision  # hard floor — never a silent approval

        if not self._always_prompt and not self._matches_review(request):
            return ApprovalDecision(approved=True)  # guarded: silent pass

        if self._confirm(request):
            return ApprovalDecision(approved=True)
        return ApprovalDecision(approved=False, reason="denied interactively by user")

    def _matches_review(self, request: ToolRequest) -> bool:
        if not self._review_patterns:
            return False
        text = request.input_text.lower()
        return any(p.lower() in text for p in self._review_patterns)

    def _prompt(self, request: ToolRequest) -> bool:
        return Confirm.ask(
            f"[woven.warning]Approve tool call?[/woven.warning] {request.input_text!r}",
            console=self._console,
            default=False,
        )
