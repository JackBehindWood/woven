from woven.settings import Config, Settings, User, resolve_runtime_config


def _config(**settings_kwargs) -> Config:
    return Config(
        user=User(id="id", name="local"), settings=Settings(**settings_kwargs)
    )


def test_resolve_runtime_config_falls_back_to_hardcoded_defaults():
    runtime = resolve_runtime_config(_config())

    assert runtime.mode == "chat"
    assert runtime.permission_mode == "guarded"
    assert runtime.model_provider is None


def test_resolve_runtime_config_uses_persisted_defaults():
    runtime = resolve_runtime_config(
        _config(default_mode="plan", default_permission_mode="manual")
    )

    assert runtime.mode == "plan"
    assert runtime.permission_mode == "manual"


def test_resolve_runtime_config_cli_override_wins_over_persisted():
    runtime = resolve_runtime_config(
        _config(default_mode="plan", default_permission_mode="manual"),
        mode="code",
        permission_mode="auto",
    )

    assert runtime.mode == "code"
    assert runtime.permission_mode == "auto"


def test_resolve_runtime_config_carries_model_provider():
    runtime = resolve_runtime_config(_config(default_model_provider="gemini"))

    assert runtime.model_provider == "gemini"
