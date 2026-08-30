from typer.testing import CliRunner

import woven.client.cli.setup_command as setup_command_module
from woven.client.cli.app import app
from woven.models import ModelError
from woven.settings import FileSecretStore, load_config
from woven.setup import CLEAR_SENTINEL, SetupService

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


def test_provider_prompt_none_clears_a_configured_provider(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )
    SetupService().set_field("model-provider", "gemini")

    result = runner.invoke(app, ["setup"], input=f"{CLEAR_SENTINEL}\n\n\nn\n")

    assert result.exit_code == 0
    assert "model provider cleared" in result.stdout
    config = load_config()
    assert config.settings.default_model_provider is None


def test_fresh_run_shows_credential_status_not_set(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(app, ["setup"], input="\n\n\nn\n")

    assert result.exit_code == 0
    assert "gemini api key: not set" in result.stdout


def test_run_with_preseeded_key_shows_credential_status_set(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )
    FileSecretStore().set("gemini_api_key", "preseeded-secret")

    result = runner.invoke(app, ["setup"], input="\n\n\nn\n")

    assert result.exit_code == 0
    assert "gemini api key: set" in result.stdout


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


def test_non_interactive_sets_mode_and_permission_mode_only():
    result = runner.invoke(
        app,
        ["setup", "--non-interactive", "--mode", "plan", "--permission-mode", "manual"],
    )

    assert result.exit_code == 0
    config = load_config()
    assert config.settings.default_mode == "plan"
    assert config.settings.default_permission_mode == "manual"
    assert config.settings.default_model_provider is None


def test_non_interactive_sets_provider_and_key_and_verifies(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(
        app,
        ["setup", "--non-interactive", "--provider", "gemini", "--api-key", "good-key"],
    )

    assert result.exit_code == 0
    assert FileSecretStore().get("gemini_api_key") == "good-key"
    config = load_config()
    assert config.settings.default_model_provider == "gemini"


def test_non_interactive_api_key_without_provider_fails_loudly():
    result = runner.invoke(app, ["setup", "--non-interactive", "--api-key", "some-key"])

    assert result.exit_code == 1
    assert "--api-key requires --provider" in result.stdout


def test_non_interactive_provider_without_api_key_fails_loudly(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(app, ["setup", "--non-interactive", "--provider", "gemini"])

    assert result.exit_code == 1
    assert "--api-key is required" in result.stdout


def test_non_interactive_invalid_provider_fails_loudly():
    result = runner.invoke(
        app,
        ["setup", "--non-interactive", "--provider", "bogus", "--api-key", "x"],
    )

    assert result.exit_code == 1
    assert "Unknown model provider" in result.stdout


def test_non_interactive_invalid_mode_fails_loudly():
    result = runner.invoke(app, ["setup", "--non-interactive", "--mode", "bogus"])

    assert result.exit_code == 1
    assert "Unknown mode" in result.stdout


def test_non_interactive_bad_key_fails_loudly_with_no_retry(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )

    result = runner.invoke(
        app,
        ["setup", "--non-interactive", "--provider", "gemini", "--api-key", "bad-key"],
    )

    assert result.exit_code == 1
    assert "invalid test key" in result.stdout


def test_non_interactive_clear_sentinel_clears_existing_provider(monkeypatch):
    monkeypatch.setitem(
        setup_command_module.MODEL_PROVIDERS, "gemini", _FakeGeminiProvider
    )
    SetupService().set_field("model-provider", "gemini")

    result = runner.invoke(
        app, ["setup", "--non-interactive", "--provider", CLEAR_SENTINEL]
    )

    assert result.exit_code == 0
    config = load_config()
    assert config.settings.default_model_provider is None


def test_non_interactive_no_flags_is_a_no_op():
    result = runner.invoke(app, ["setup", "--non-interactive"])

    assert result.exit_code == 0
    config = load_config()
    assert config.settings.default_mode == "chat"
    assert config.settings.default_permission_mode == "guarded"
    assert config.settings.default_model_provider is None
