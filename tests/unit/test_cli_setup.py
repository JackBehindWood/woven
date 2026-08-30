from typer.testing import CliRunner

import woven.client.cli.setup_command as setup_command_module
from woven.client.cli.app import app
from woven.models import ModelError
from woven.settings import FileSecretStore, load_config
from woven.setup import SetupService

runner = CliRunner()


class _FakeGeminiProvider:
    SETUP_HINT = "Get a fake key from Fake AI Studio."

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def check_connection(self) -> None:
        if self.api_key != "good-key":
            raise ModelError("invalid test key")


def test_fresh_run_skips_provider_and_keeps_defaults(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(app, ["setup"], input="\n\n\nn\n")

    assert result.exit_code == 0
    config = load_config()
    assert config.settings.default_model_provider is None
    assert config.settings.default_mode == "chat"
    assert config.settings.default_permission_mode == "guarded"


def test_rerun_shows_prior_values_as_defaults(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )
    SetupService().set_field("mode", "plan")
    SetupService().set_field("permission-mode", "manual")

    result = runner.invoke(app, ["setup"], input="\n\n\nn\n")

    assert result.exit_code == 0
    assert "[plan]" in result.stdout
    assert "[manual]" in result.stdout
    config = load_config()
    assert config.settings.default_mode == "plan"
    assert config.settings.default_permission_mode == "manual"


def test_key_validation_retries_then_succeeds(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(
        app,
        ["setup"],
        input="gemini\nbad-key-1\nbad-key-2\ngood-key\n\n\nn\n",
    )

    assert result.exit_code == 0
    assert "connection verified" in result.stdout
    assert FileSecretStore().get("gemini_api_key") == "good-key"
    config = load_config()
    assert config.settings.default_model_provider == "gemini"


def test_key_validation_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(
        app,
        ["setup"],
        input="gemini\nbad-key-1\nbad-key-2\nbad-key-3\n\n\nn\n",
    )

    assert result.exit_code == 0
    assert "Could not verify" in result.stdout
    config = load_config()
    assert config.settings.default_model_provider == "gemini"


def test_declining_doctor_offer_does_not_render_diagnostics(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(app, ["setup"], input="\n\n\nn\n")

    assert result.exit_code == 0
    assert "dependencies" not in result.stdout


def test_accepting_doctor_offer_renders_diagnostics(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(app, ["setup"], input="\n\n\ny\n")

    assert result.exit_code == 0
    assert "dependencies" in result.stdout
    assert "ok," in result.stdout or "warn," in result.stdout
