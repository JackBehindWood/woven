import json
import os

from woven.settings import (
    Config,
    ConfigError,
    FileSecretStore,
    Settings,
    User,
    config_dir,
    config_path,
    load_config,
    save_config,
)


def test_config_dir_respects_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom"))

    assert config_dir() == tmp_path / "custom" / "woven"


def test_load_config_creates_and_persists_defaults_on_missing_file():
    config = load_config()

    assert config.settings == Settings()
    assert config_path().exists()
    assert (config_path().stat().st_mode & 0o777) == 0o600


def test_load_config_round_trips_a_saved_file():
    original = Config(
        user=User(id="fixed-id", name="local"),
        settings=Settings(default_mode="plan"),
    )
    save_config(original)

    loaded = load_config()

    assert loaded == original


def test_load_config_raises_config_error_on_corrupt_json():
    config_dir().mkdir(parents=True, exist_ok=True)
    config_path().write_text("not json")

    try:
        load_config()
        raise AssertionError("expected ConfigError")
    except ConfigError:
        pass


def test_save_config_always_results_in_mode_0600():
    config = Config(user=User(id="id", name="local"), settings=Settings())
    save_config(config)
    os.chmod(config_path(), 0o644)

    save_config(config)

    assert (config_path().stat().st_mode & 0o777) == 0o600


def test_load_config_self_heals_looser_permissions():
    config = Config(user=User(id="id", name="local"), settings=Settings())
    save_config(config)
    os.chmod(config_path(), 0o644)

    load_config()

    assert (config_path().stat().st_mode & 0o777) == 0o600


def test_user_id_stable_across_repeated_loads():
    first = load_config()
    second = load_config()

    assert first.user.id == second.user.id


def test_load_config_migrates_legacy_gemini_api_key():
    config_dir().mkdir(parents=True, exist_ok=True)
    legacy_payload = {
        "user": {"id": "fixed-id", "name": "local"},
        "settings": {
            "default_mode": "chat",
            "default_permission_mode": "guarded",
            "default_model_provider": None,
            "gemini_api_key": "legacy-secret",
        },
    }
    config_path().write_text(json.dumps(legacy_payload))

    config = load_config()

    assert FileSecretStore().get("gemini_api_key") == "legacy-secret"
    assert "gemini_api_key" not in config_path().read_text()
    assert config.settings.default_mode == "chat"


def test_load_config_with_no_legacy_key_does_not_touch_secrets():
    config = load_config()

    save_config(config)

    assert FileSecretStore().get("gemini_api_key") is None
