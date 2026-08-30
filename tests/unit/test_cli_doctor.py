import json

from typer.testing import CliRunner

import woven.client.cli.doctor_command as doctor_command_module
from woven.client.cli.app import app

runner = CliRunner()


def _patch_service(monkeypatch, run_all_result):
    class _FakeService:
        def run_all(self):
            return run_all_result

    monkeypatch.setattr(
        doctor_command_module, "DiagnosticService", lambda: _FakeService()
    )


def test_doctor_on_clean_config_exits_0():
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "environment" in result.stdout
    assert "dependencies" in result.stdout


def test_doctor_exits_1_when_a_check_fails(monkeypatch):
    from woven.diagnostics import CheckStatus, DiagnosticCheck

    _patch_service(
        monkeypatch,
        [
            DiagnosticCheck(
                name="provider",
                status=CheckStatus.FAIL,
                message="gemini is not reachable.",
                fix_hint="invalid test key",
            )
        ],
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "invalid test key" in result.stdout


def test_doctor_json_output_is_valid_and_parseable():
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert {"name", "status", "message", "fix_hint"} <= payload[0].keys()


def test_doctor_json_exits_1_on_failure(monkeypatch):
    from woven.diagnostics import CheckStatus, DiagnosticCheck

    _patch_service(
        monkeypatch,
        [
            DiagnosticCheck(
                name="provider",
                status=CheckStatus.FAIL,
                message="gemini is not reachable.",
                fix_hint="invalid test key",
            )
        ],
    )

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload[0]["status"] == "fail"
