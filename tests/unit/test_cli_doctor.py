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


def test_doctor_quiet_hides_ok_checks_but_keeps_warn_and_summary(monkeypatch):
    from woven.diagnostics import CheckStatus, DiagnosticCheck

    _patch_service(
        monkeypatch,
        [
            DiagnosticCheck(name="environment", status=CheckStatus.OK, message="fine"),
            DiagnosticCheck(
                name="config:mode", status=CheckStatus.WARN, message="stale mode"
            ),
        ],
    )

    result = runner.invoke(app, ["doctor", "--quiet"])

    assert result.exit_code == 0
    assert "environment" not in result.stdout
    assert "config:mode" in result.stdout
    assert "1 ok, 1 warn, 0 fail" in result.stdout


def test_doctor_fix_resets_stale_config_and_shows_fix_panel():
    from woven.settings import Config, Settings, User, save_config

    save_config(
        Config(
            user=User(id="id", name="local"),
            settings=Settings(default_mode="bogus"),
        )
    )

    result = runner.invoke(app, ["doctor", "--fix"])

    assert result.exit_code == 0
    assert "doctor --fix" in result.stdout
    assert "config:mode" in result.stdout

    from woven.settings import load_config

    assert load_config().settings.default_mode == "chat"


def test_doctor_fix_is_a_no_op_on_clean_config():
    result = runner.invoke(app, ["doctor", "--fix"])

    assert result.exit_code == 0
    assert "doctor --fix" not in result.stdout


def test_doctor_fix_never_flips_a_fail_check(monkeypatch):
    from woven.diagnostics import CheckStatus, DiagnosticCheck

    class _FakeService:
        def fix_config_validity(self):
            return []

        def run_all(self):
            return [
                DiagnosticCheck(
                    name="provider",
                    status=CheckStatus.FAIL,
                    message="gemini is not reachable.",
                )
            ]

    monkeypatch.setattr(
        doctor_command_module, "DiagnosticService", lambda: _FakeService()
    )

    result = runner.invoke(app, ["doctor", "--fix"])

    assert result.exit_code == 1
