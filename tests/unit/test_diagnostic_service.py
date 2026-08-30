import os

from woven.diagnostics import CheckStatus, DiagnosticService
from woven.models import ModelError
from woven.settings import (
    PROVIDER_ENV_VARS,
    Config,
    FileSecretStore,
    Settings,
    User,
    config_dir,
    load_config,
    save_config,
)


class _FakeProvider:
    SETUP_HINT = "Get a key from Fake AI Studio."

    def __init__(self, api_key: str, *, error: Exception | None = None):
        self.api_key = api_key
        self._error = error

    def check_connection(self) -> None:
        if self._error is not None:
            raise self._error


def _fake_provider_factory(error: Exception | None = None):
    def factory(api_key: str) -> _FakeProvider:
        return _FakeProvider(api_key, error=error)

    factory.SETUP_HINT = _FakeProvider.SETUP_HINT
    return factory


def _status_by_name(checks, name: str) -> CheckStatus:
    return next(c.status for c in checks if c.name == name)


def test_check_environment_ok_on_fresh_config():
    service = DiagnosticService()

    check = service.check_environment()

    assert check.status == CheckStatus.OK


def test_check_environment_fails_on_loosened_permissions():
    load_config()
    os.chmod(config_dir(), 0o755)
    service = DiagnosticService()

    check = service.check_environment()

    assert check.status == CheckStatus.FAIL
    assert "0o700" in check.message


def test_check_dependencies_ok_when_google_genai_importable():
    service = DiagnosticService()

    check = service.check_dependencies()

    assert check.status == CheckStatus.OK


def test_check_config_validity_ok_on_default_config():
    service = DiagnosticService()

    checks = service.check_config_validity()

    assert {c.status for c in checks} == {CheckStatus.OK}


def test_check_config_validity_warns_on_stale_mode():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_mode="bogus"),
    )
    save_config(config)
    service = DiagnosticService()

    checks = service.check_config_validity()

    assert _status_by_name(checks, "config:mode") == CheckStatus.WARN


def test_check_config_validity_warns_on_stale_permission_mode():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_permission_mode="bogus"),
    )
    save_config(config)
    service = DiagnosticService()

    checks = service.check_config_validity()

    assert _status_by_name(checks, "config:permission-mode") == CheckStatus.WARN


def test_check_config_validity_warns_on_stale_model_provider():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_model_provider="bogus"),
    )
    save_config(config)
    service = DiagnosticService(model_providers={"gemini": _fake_provider_factory()})

    checks = service.check_config_validity()

    assert _status_by_name(checks, "config:model-provider") == CheckStatus.WARN


def test_check_credentials_warns_with_setup_hint_when_missing():
    service = DiagnosticService(
        secret_store=FileSecretStore(),
        model_providers={"gemini": _fake_provider_factory()},
    )

    checks = service.check_credentials()

    check = next(c for c in checks if c.name == "credentials:gemini")
    assert check.status == CheckStatus.WARN
    assert "Fake AI Studio" in check.fix_hint


def test_check_credentials_ok_when_key_configured():
    store = FileSecretStore()
    store.set("gemini_api_key", "secret")
    service = DiagnosticService(secret_store=store)

    checks = service.check_credentials()

    assert _status_by_name(checks, "credentials:gemini") == CheckStatus.OK


def test_check_credentials_ok_message_names_env_source(monkeypatch):
    monkeypatch.setenv(PROVIDER_ENV_VARS["gemini"], "env-key")
    service = DiagnosticService(secret_store=FileSecretStore())

    checks = service.check_credentials()

    check = next(c for c in checks if c.name == "credentials:gemini")
    assert "environment variable" in check.message


def test_check_credentials_ok_message_names_file_source(monkeypatch):
    monkeypatch.delenv(PROVIDER_ENV_VARS["gemini"], raising=False)
    store = FileSecretStore()
    store.set("gemini_api_key", "secret")
    service = DiagnosticService(secret_store=store)

    checks = service.check_credentials()

    check = next(c for c in checks if c.name == "credentials:gemini")
    assert "secrets file" in check.message


def test_check_provider_reachable_warns_when_no_default_provider():
    service = DiagnosticService()

    check = service.check_provider_reachable()

    assert check.status == CheckStatus.WARN


def test_check_provider_reachable_fails_when_no_api_key():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_model_provider="gemini"),
    )
    save_config(config)
    service = DiagnosticService(model_providers={"gemini": _fake_provider_factory()})

    check = service.check_provider_reachable()

    assert check.status == CheckStatus.FAIL
    assert "No API key" in check.message


def test_check_provider_reachable_ok_when_connection_succeeds():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_model_provider="gemini"),
    )
    save_config(config)
    store = FileSecretStore()
    store.set("gemini_api_key", "secret")
    service = DiagnosticService(
        secret_store=store, model_providers={"gemini": _fake_provider_factory()}
    )

    check = service.check_provider_reachable()

    assert check.status == CheckStatus.OK


def test_check_provider_reachable_fails_when_connection_raises():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_model_provider="gemini"),
    )
    save_config(config)
    store = FileSecretStore()
    store.set("gemini_api_key", "secret")
    service = DiagnosticService(
        secret_store=store,
        model_providers={"gemini": _fake_provider_factory(ModelError("invalid key"))},
    )

    check = service.check_provider_reachable()

    assert check.status == CheckStatus.FAIL
    assert check.fix_hint == "invalid key"


def test_run_all_returns_all_checks_in_fixed_order():
    service = DiagnosticService()

    checks = service.run_all()
    names = [c.name for c in checks]

    assert names == [
        "environment",
        "dependencies",
        "config:mode",
        "config:permission-mode",
        "config:model-provider",
        "credentials:gemini",
        "provider",
    ]


def test_fix_config_validity_resets_stale_mode_and_permission_mode():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_mode="bogus", default_permission_mode="bogus"),
    )
    save_config(config)
    service = DiagnosticService()

    messages = service.fix_config_validity()

    assert len(messages) == 2
    updated = load_config()
    assert updated.settings.default_mode == "chat"
    assert updated.settings.default_permission_mode == "guarded"


def test_fix_config_validity_clears_stale_model_provider():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_model_provider="bogus"),
    )
    save_config(config)
    service = DiagnosticService(model_providers={"gemini": _fake_provider_factory()})

    messages = service.fix_config_validity()

    assert len(messages) == 1
    assert load_config().settings.default_model_provider is None


def test_fix_config_validity_no_ops_on_clean_config():
    service = DiagnosticService()

    messages = service.fix_config_validity()

    assert messages == []


def test_fix_config_validity_never_touches_credentials_or_provider_checks():
    config = Config(
        user=User(id="id", name="local"),
        settings=Settings(default_mode="bogus"),
    )
    save_config(config)
    service = DiagnosticService(model_providers={"gemini": _fake_provider_factory()})

    before_credentials = service.check_credentials()
    before_provider = service.check_provider_reachable()

    service.fix_config_validity()

    after_credentials = service.check_credentials()
    after_provider = service.check_provider_reachable()
    assert [c.status for c in before_credentials] == [
        c.status for c in after_credentials
    ]
    assert before_provider.status == after_provider.status


def test_no_check_makes_network_call_when_nothing_configured():
    calls: list[str] = []

    class _NoisyProvider:
        SETUP_HINT = "hint"

        def __init__(self, api_key: str) -> None:
            calls.append(api_key)

        def check_connection(self) -> None:
            calls.append("check_connection")

    service = DiagnosticService(model_providers={"gemini": _NoisyProvider})

    service.run_all()

    assert calls == []
