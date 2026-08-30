import pytest

from woven.settings import FileSecretStore, load_config
from woven.setup import SetupError, SetupService


def test_current_config_returns_persisted_config():
    service = SetupService()

    config = service.current_config()

    assert config.settings.default_mode == "chat"


def test_set_field_persists_valid_value_and_returns_updated_config():
    service = SetupService()

    updated = service.set_field("mode", "plan")

    assert updated.settings.default_mode == "plan"
    assert load_config().settings.default_mode == "plan"


def test_set_field_unknown_field_raises_setup_error():
    service = SetupService()

    with pytest.raises(SetupError, match="Unknown setting"):
        service.set_field("bogus", "x")


def test_set_field_invalid_value_raises_setup_error_and_leaves_config_unchanged():
    service = SetupService()
    before = load_config()

    with pytest.raises(SetupError, match="Unknown mode"):
        service.set_field("mode", "bogus")

    assert load_config() == before


def test_set_secret_persists_to_secret_store():
    store = FileSecretStore()
    service = SetupService(secret_store=store)

    service.set_secret("gemini", "super-secret")

    assert store.get("gemini_api_key") == "super-secret"


def test_set_secret_unknown_provider_raises_setup_error():
    service = SetupService()

    with pytest.raises(SetupError, match="Unknown model provider"):
        service.set_secret("bogus", "x")
