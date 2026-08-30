from __future__ import annotations

import json
from dataclasses import asdict

import typer

from woven.client.cli.console import make_console
from woven.client.cli.registry import register_command
from woven.client.cli.render import render_diagnostics, render_status_panel
from woven.diagnostics import CheckStatus, DiagnosticService


@register_command("doctor")
def doctor_command(
    as_json: bool = typer.Option(
        False, "--json", help="Print checks as a JSON array instead of a panel."
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Only print non-OK checks and the summary line (human-readable output "
        "only).",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Auto-correct safely-fixable config warnings (stale mode/"
        "permission-mode/model-provider) before reporting.",
    ),
) -> None:
    """Run structured diagnostics against the current environment and config."""
    service = DiagnosticService()

    fix_messages: list[str] = []
    if fix:
        fix_messages = service.fix_config_validity()

    checks = service.run_all()

    if as_json:
        typer.echo(json.dumps([asdict(check) for check in checks]))
    else:
        console = make_console()
        if fix_messages:
            render_status_panel(console, "doctor --fix", fix_messages)
        render_diagnostics(console, checks, only_failures=quiet)

    if any(check.status == CheckStatus.FAIL for check in checks):
        raise typer.Exit(code=1)
