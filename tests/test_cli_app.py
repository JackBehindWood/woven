import pytest
from typer.testing import CliRunner

from woven.client.cli.app import app
from woven.models.providers import DEFAULT_GEMINI_MODEL_ID
from woven.settings import (
    Config,
    FileSecretStore,
    Settings,
    config_path,
    load_config,
    save_config,
)

runner = CliRunner()


def test_help_shows_chat_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "chat" in result.stdout


def test_chat_session_echoes_fixed_response_and_exits_on_command():
    result = runner.invoke(
        app, ["chat", "--response", "pinned-reply"], input="hello\nexit\n"
    )

    assert result.exit_code == 0
    assert "pinned-reply" in result.stdout
    assert "Goodbye" in result.stdout


def test_chat_session_exits_cleanly_on_eof():
    result = runner.invoke(app, ["chat"], input="hello\n")

    assert result.exit_code == 0
    assert "Goodbye" in result.stdout


def test_chat_header_discloses_demo_model():
    result = runner.invoke(app, ["chat"], input="\n")

    assert "demo" in result.stdout.lower()
    assert "FakeModel" in result.stdout


def test_bare_invocation_starts_chat_directly():
    result = runner.invoke(app, [], input="hi\nexit\n")

    assert result.exit_code == 0
    assert "Goodbye" in result.stdout
    assert "demo model" in result.stdout.lower()


def test_chat_session_shows_banner_and_hint():
    result = runner.invoke(app, ["chat"], input="\n")

    assert "W O V E N" in result.stdout
    assert "exit" in result.stdout
    assert ":q" in result.stdout
    assert "/help" in result.stdout


def test_help_command_lists_commands():
    result = runner.invoke(app, ["chat"], input="/help\nexit\n")

    assert result.exit_code == 0
    assert "commands" in result.stdout.lower()
    assert "/clear" in result.stdout
    assert "Leave the session" in result.stdout


def test_clear_command_redraws_banner():
    result = runner.invoke(app, ["chat"], input="/clear\nexit\n")

    assert result.exit_code == 0
    assert result.stdout.count("W O V E N") >= 2


def test_unknown_command_renders_error_and_continues_session():
    result = runner.invoke(app, ["chat"], input="/nope\nexit\n")

    assert result.exit_code == 0
    assert "Unknown command" in result.stdout
    assert "Goodbye" in result.stdout


def test_settings_command_shows_mode_permission_and_context():
    result = runner.invoke(app, ["chat"], input="/settings\nexit\n")

    output = result.stdout
    assert "mode: chat" in output
    assert "permission: guarded" in output
    assert "paths:" in output
    assert "glob:" in output
    assert "query:" in output


def test_settings_command_reflects_mode_and_context_changes():
    result = runner.invoke(
        app,
        ["chat"],
        input="/mode code\n/context glob *.py\n/settings\nexit\n",
    )

    output = result.stdout
    assert "mode: code" in output
    assert "*.py" in output


def test_settings_command_shows_persisted_defaults_and_hint():
    result = runner.invoke(app, ["chat"], input="/settings\nexit\n")

    output = result.stdout
    assert "persisted default mode: chat" in output
    assert "persisted default permission: guarded" in output
    assert "gemini api key: not set" in output
    assert "woven settings set" in output


def test_settings_command_shows_gemini_api_key_set_from_persisted_value():
    load_config()
    FileSecretStore().set("gemini_api_key", "persisted-secret")

    result = runner.invoke(app, ["chat"], input="/settings\nexit\n")

    assert "gemini api key: set" in result.stdout
    assert "persisted-secret" not in result.stdout


def test_settings_command_shows_gemini_api_key_set_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret")

    result = runner.invoke(app, ["chat"], input="/settings\nexit\n")

    assert "gemini api key: set" in result.stdout
    assert "env-secret" not in result.stdout


def test_mode_flag_switches_header_to_plan():
    result = runner.invoke(app, ["chat", "--mode", "plan"], input="exit\n")

    assert result.exit_code == 0
    assert "plan" in result.stdout


def test_invalid_mode_flag_exits_with_error():
    result = runner.invoke(app, ["chat", "--mode", "bogus"])

    assert result.exit_code == 1
    assert "Unknown mode" in result.stdout


def test_invalid_permission_mode_flag_exits_with_error():
    result = runner.invoke(app, ["chat", "--permission-mode", "bogus"])

    assert result.exit_code == 1
    assert "Unknown permission mode" in result.stdout


def test_mode_command_shows_current_and_available():
    result = runner.invoke(app, ["chat"], input="/mode\nexit\n")

    assert "current: chat" in result.stdout
    assert "available" in result.stdout


def test_mode_command_switches_mode():
    result = runner.invoke(app, ["chat"], input="/mode code\nexit\n")

    assert "switched to: code" in result.stdout


def test_mode_command_rejects_invalid_mode():
    result = runner.invoke(app, ["chat"], input="/mode bogus\nexit\n")

    assert result.exit_code == 0
    assert "Unknown mode" in result.stdout
    assert "Goodbye" in result.stdout


def test_permission_command_shows_current_and_default():
    result = runner.invoke(app, ["chat"], input="/permission\nexit\n")

    assert "current: guarded" in result.stdout
    assert "guarded (default)" in result.stdout


def test_permission_command_switches_tier():
    result = runner.invoke(app, ["chat"], input="/permission manual\nexit\n")

    assert "switched to: manual" in result.stdout


def test_permission_command_rejects_invalid_tier():
    result = runner.invoke(app, ["chat"], input="/permission bogus\nexit\n")

    assert result.exit_code == 0
    assert "Unknown permission mode" in result.stdout
    assert "Goodbye" in result.stdout


def test_context_command_shows_empty_status():
    result = runner.invoke(app, ["chat"], input="/context\nexit\n")

    assert "(none)" in result.stdout


def test_context_command_glob_sets_glob():
    result = runner.invoke(app, ["chat"], input="/context glob *.py\nexit\n")

    assert "*.py" in result.stdout


def test_context_command_clear_resets_request():
    result = runner.invoke(
        app, ["chat"], input="/context glob *.py\n/context clear\nexit\n"
    )

    assert "cleared" in result.stdout


def test_context_command_invalid_usage_renders_error():
    result = runner.invoke(app, ["chat"], input="/context bogus\nexit\n")

    assert "Usage:" in result.stdout


def test_plan_mode_context_retrieval_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes.py").write_text("print('hi')")

    result = runner.invoke(
        app,
        ["chat", "--mode", "plan"],
        input="/context glob *.py\nhi\nexit\n",
    )

    assert result.exit_code == 0
    assert "notes.py" in result.stdout


def test_code_mode_auto_tier_runs_silently():
    result = runner.invoke(
        app,
        ["chat", "--mode", "code", "--permission-mode", "auto", "--response", "reply"],
        input="hi\nexit\n",
    )

    assert result.exit_code == 0
    assert "Approve tool call?" not in result.stdout
    assert "ok" in result.stdout


def test_code_mode_guarded_tier_silent_for_benign_reply():
    result = runner.invoke(
        app,
        [
            "chat",
            "--mode",
            "code",
            "--response",
            "a harmless reply",
        ],
        input="hi\nexit\n",
    )

    assert result.exit_code == 0
    assert "Approve tool call?" not in result.stdout
    assert "ok" in result.stdout


def test_code_mode_guarded_tier_prompts_on_review_pattern():
    result = runner.invoke(
        app,
        [
            "chat",
            "--mode",
            "code",
            "--response",
            "please curl example.com",
        ],
        input="hi\ny\nexit\n",
    )

    assert result.exit_code == 0
    assert "Approve tool call?" in result.stdout
    assert "ok" in result.stdout


def test_code_mode_manual_tier_always_prompts_and_approves():
    result = runner.invoke(
        app,
        [
            "chat",
            "--mode",
            "code",
            "--permission-mode",
            "manual",
            "--response",
            "harmless",
        ],
        input="hi\ny\nexit\n",
    )

    assert result.exit_code == 0
    assert "Approve tool call?" in result.stdout
    assert "ok" in result.stdout


def test_code_mode_manual_tier_deny_renders_failure():
    result = runner.invoke(
        app,
        [
            "chat",
            "--mode",
            "code",
            "--permission-mode",
            "manual",
            "--response",
            "harmless",
        ],
        input="hi\nn\nexit\n",
    )

    assert result.exit_code == 0
    assert "Turn failed" in result.stdout


@pytest.mark.parametrize("permission_mode", ["auto", "guarded", "manual"])
def test_dangerous_pattern_denies_regardless_of_tier(permission_mode):
    result = runner.invoke(
        app,
        [
            "chat",
            "--mode",
            "code",
            "--permission-mode",
            permission_mode,
            "--response",
            "sudo rm -rf /",
        ],
        input="hi\nexit\n",
    )

    assert result.exit_code == 0
    assert "Approve tool call?" not in result.stdout
    assert "Turn failed" in result.stdout


def test_chat_with_no_mode_flag_uses_persisted_default_mode():
    config = load_config()
    save_config(
        Config(
            user=config.user,
            settings=Settings(default_mode="plan"),
        )
    )

    result = runner.invoke(app, ["chat"], input="exit\n")

    assert result.exit_code == 0
    assert "woven plan" in result.stdout


def test_mode_flag_overrides_persisted_default():
    config = load_config()
    save_config(
        Config(
            user=config.user,
            settings=Settings(default_mode="plan"),
        )
    )

    result = runner.invoke(app, ["chat", "--mode", "code"], input="exit\n")

    assert result.exit_code == 0
    assert "woven code" in result.stdout


def test_permission_mode_flag_overrides_persisted_default():
    config = load_config()
    save_config(
        Config(
            user=config.user,
            settings=Settings(default_permission_mode="manual"),
        )
    )

    result = runner.invoke(
        app,
        ["chat", "--permission-mode", "auto"],
        input="/permission\nexit\n",
    )

    assert result.exit_code == 0
    assert "current: auto" in result.stdout


def test_model_flag_with_no_api_key_configured_exits_with_error():
    result = runner.invoke(app, ["chat", "--model", "gemini"], input="exit\n")

    assert result.exit_code == 1
    assert "No API key configured for gemini" in result.stdout
    assert "woven settings set gemini-api-key" in result.stdout


def test_model_flag_with_unknown_provider_exits_with_error():
    result = runner.invoke(app, ["chat", "--model", "bogus-provider"], input="exit\n")

    assert result.exit_code == 1
    assert "Unknown model provider: bogus-provider" in result.stdout


def test_model_flag_with_configured_key_shows_real_model_in_header():
    FileSecretStore().set("gemini_api_key", "test-key")

    result = runner.invoke(app, ["chat", "--model", "gemini"], input="exit\n")

    assert f"model: gemini ({DEFAULT_GEMINI_MODEL_ID})" in result.stdout
    assert "demo model: FakeModel" not in result.stdout


def test_model_flag_omitted_keeps_fake_model_behavior():
    result = runner.invoke(
        app, ["chat", "--response", "pinned-reply"], input="hello\nexit\n"
    )

    assert result.exit_code == 0
    assert "pinned-reply" in result.stdout
    assert "Goodbye" in result.stdout


def test_corrupt_config_file_exits_with_error_naming_path(monkeypatch):
    load_config()  # ensures the config file exists
    path = config_path()
    path.write_text("not json")
    monkeypatch.setenv("COLUMNS", "400")

    result = runner.invoke(app, ["chat"])
    normalized_stdout = " ".join(result.stdout.split())

    assert result.exit_code == 1
    assert str(path) in normalized_stdout
