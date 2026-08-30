import os

from woven.settings import (
    PROVIDER_ENV_VARS,
    FileSecretStore,
    resolve_api_key,
    resolve_api_key_with_source,
)
from woven.settings.secrets import secrets_path


def test_get_on_missing_file_returns_none():
    store = FileSecretStore()

    assert store.get("gemini_api_key") is None


def test_set_then_get_round_trips_value():
    store = FileSecretStore()

    store.set("gemini_api_key", "super-secret")

    assert store.get("gemini_api_key") == "super-secret"


def test_set_persists_to_disk_with_mode_0600():
    store = FileSecretStore()

    store.set("gemini_api_key", "super-secret")

    assert secrets_path().exists()
    assert (secrets_path().stat().st_mode & 0o777) == 0o600


def test_delete_removes_a_key():
    store = FileSecretStore()
    store.set("gemini_api_key", "super-secret")

    store.delete("gemini_api_key")

    assert store.get("gemini_api_key") is None


def test_delete_missing_key_is_a_no_op():
    store = FileSecretStore()

    store.delete("gemini_api_key")

    assert store.get("gemini_api_key") is None


def test_set_self_heals_looser_permissions():
    store = FileSecretStore()
    store.set("gemini_api_key", "super-secret")
    os.chmod(secrets_path(), 0o644)

    store.get("gemini_api_key")

    assert (secrets_path().stat().st_mode & 0o777) == 0o600


def test_resolve_api_key_env_wins_over_store(monkeypatch):
    monkeypatch.setenv(PROVIDER_ENV_VARS["gemini"], "env-key")
    store = FileSecretStore()
    store.set("gemini_api_key", "persisted-key")

    assert resolve_api_key(store, "gemini") == "env-key"


def test_resolve_api_key_falls_back_to_store(monkeypatch):
    monkeypatch.delenv(PROVIDER_ENV_VARS["gemini"], raising=False)
    store = FileSecretStore()
    store.set("gemini_api_key", "persisted-key")

    assert resolve_api_key(store, "gemini") == "persisted-key"


def test_resolve_api_key_returns_none_when_neither_set(monkeypatch):
    monkeypatch.delenv(PROVIDER_ENV_VARS["gemini"], raising=False)
    store = FileSecretStore()

    assert resolve_api_key(store, "gemini") is None


def test_resolve_api_key_unknown_provider_falls_back_to_store():
    store = FileSecretStore()
    store.set("mystery_api_key", "persisted-key")

    assert resolve_api_key(store, "mystery") == "persisted-key"


def test_resolve_api_key_with_source_env_wins(monkeypatch):
    monkeypatch.setenv(PROVIDER_ENV_VARS["gemini"], "env-key")
    store = FileSecretStore()
    store.set("gemini_api_key", "persisted-key")

    assert resolve_api_key_with_source(store, "gemini") == ("env-key", "env")


def test_resolve_api_key_with_source_falls_back_to_file(monkeypatch):
    monkeypatch.delenv(PROVIDER_ENV_VARS["gemini"], raising=False)
    store = FileSecretStore()
    store.set("gemini_api_key", "persisted-key")

    assert resolve_api_key_with_source(store, "gemini") == ("persisted-key", "file")


def test_resolve_api_key_with_source_returns_none_when_neither_set(monkeypatch):
    monkeypatch.delenv(PROVIDER_ENV_VARS["gemini"], raising=False)
    store = FileSecretStore()

    assert resolve_api_key_with_source(store, "gemini") is None
