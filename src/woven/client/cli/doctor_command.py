from __future__ import annotations

import json
from dataclasses import asdict

import typer

from woven.client.cli.console import make_console
from woven.client.cli.registry import register_command
from woven.client.cli.render import render_diagnostics
from woven.diagnostics import CheckStatus, DiagnosticService


@register_command("doctor")
def doctor_command(
    as_json: bool = typer.Option(
        False, "--json", help="Print checks as a JSON array instead of a panel."
    ),
) -> None:
    """Run structured diagnostics against the current environment and config."""
    checks = DiagnosticService().run_all()

    if as_json:
        typer.echo(json.dumps([asdict(check) for check in checks]))
    else:
        console = make_console()
        render_diagnostics(console, checks)

    if any(check.status == CheckStatus.FAIL for check in checks):
        raise typer.Exit(code=1)
