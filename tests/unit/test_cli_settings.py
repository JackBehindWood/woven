from typer.testing import CliRunner

from woven.client.cli.app import app
from woven.settings import FileSecretStore, config_path, load_config
from woven.settings.secrets import secrets_path

runner = CliRunner()


def test_settings_show_on_fresh_config_prints_defaults():
    result = runner.invoke(app, ["settings", "show"])

    assert result.exit_code == 0
    assert "default mode: chat" in result.stdout
    assert "default permission: guarded" in result.stdout
    assert "gemini api key: not set" in result.stdout


def test_settings_set_mode_persists_and_show_reflects_it():
    set_result = runner.invoke(app, ["settings", "set", "mode", "plan"])
    assert set_result.exit_code == 0

    show_result = runner.invoke(app, ["settings", "show"])

    assert "default mode: plan" in show_result.stdout


def test_settings_set_gemini_api_key_persists_to_secrets_file_but_hides_stdout():
    result = runner.invoke(app, ["settings", "set", "gemini-api-key", "super-secret"])

    assert result.exit_code == 0
    assert "super-secret" not in result.stdout
    assert "(hidden)" in result.stdout

    raw_secrets_contents = secrets_path().read_text()
    assert "super-secret" in raw_secrets_contents
    assert not config_path().exists()


def test_settings_set_gemini_api_key_without_value_prompts_hidden():
    result = runner.invoke(
        app, ["settings", "set", "gemini-api-key"], input="prompted-secret\n"
    )

    assert result.exit_code == 0
    assert "prompted-secret" not in result.stdout
    assert FileSecretStore().get("gemini_api_key") == "prompted-secret"


def test_settings_set_plain_field_without_value_exits_1():
    result = runner.invoke(app, ["settings", "set", "mode"])

    assert result.exit_code == 1
    assert "Value is required" in result.stdout


def test_settings_set_unknown_field_lists_all_known_fields():
    result = runner.invoke(app, ["settings", "set", "bogus-field", "x"])

    assert result.exit_code == 1
    assert "gemini-api-key" in result.stdout
    assert "mode" in result.stdout


def test_settings_set_invalid_mode_exits_1_and_leaves_file_unchanged():
    load_config()
    before = config_path().read_text()

    result = runner.invoke(app, ["settings", "set", "mode", "bogus"])

    assert result.exit_code == 1
    assert "Unknown mode" in result.stdout
    assert config_path().read_text() == before


def test_settings_set_invalid_permission_mode_exits_1_and_leaves_file_unchanged():
    load_config()
    before = config_path().read_text()

    result = runner.invoke(app, ["settings", "set", "permission-mode", "bogus"])

    assert result.exit_code == 1
    assert "Unknown permission mode" in result.stdout
    assert config_path().read_text() == before


def test_settings_set_model_provider_gemini_succeeds():
    result = runner.invoke(app, ["settings", "set", "model-provider", "gemini"])

    assert result.exit_code == 0

    show_result = runner.invoke(app, ["settings", "show"])
    assert "default model provider: gemini" in show_result.stdout


def test_settings_set_model_provider_none_clears_a_configured_provider():
    set_result = runner.invoke(app, ["settings", "set", "model-provider", "gemini"])
    assert set_result.exit_code == 0

    clear_result = runner.invoke(app, ["settings", "set", "model-provider", "none"])
    assert clear_result.exit_code == 0

    show_result = runner.invoke(app, ["settings", "show"])
    assert "default model provider: (none)" in show_result.stdout


def test_settings_set_model_provider_bogus_exits_1_and_leaves_file_unchanged():
    load_config()
    before = config_path().read_text()

    result = runner.invoke(app, ["settings", "set", "model-provider", "bogus"])

    assert result.exit_code == 1
    assert "Unknown model provider" in result.stdout
    assert config_path().read_text() == before


def test_settings_show_under_corrupt_config_exits_1_naming_path(monkeypatch):
    load_config()
    path = config_path()
    path.write_text("not json")
    monkeypatch.setenv("COLUMNS", "400")

    result = runner.invoke(app, ["settings", "show"])
    normalized_stdout = " ".join(result.stdout.split())

    assert result.exit_code == 1
    assert str(path) in normalized_stdout


def test_settings_set_under_corrupt_config_exits_1_naming_path(monkeypatch):
    load_config()
    path = config_path()
    path.write_text("not json")
    monkeypatch.setenv("COLUMNS", "400")

    result = runner.invoke(app, ["settings", "set", "mode", "plan"])
    normalized_stdout = " ".join(result.stdout.split())

    assert result.exit_code == 1
    assert str(path) in normalized_stdout
