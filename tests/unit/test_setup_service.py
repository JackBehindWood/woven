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


def test_set_field_model_provider_none_clears_a_configured_provider():
    service = SetupService()
    service.set_field("model-provider", "gemini")

    updated = service.set_field("model-provider", "none")

    assert updated.settings.default_model_provider is None
    assert load_config().settings.default_model_provider is None


def test_set_field_model_provider_none_on_fresh_config_is_a_no_op():
    service = SetupService()

    updated = service.set_field("model-provider", "none")

    assert updated.settings.default_model_provider is None


def test_has_secret_false_when_not_configured():
    service = SetupService(secret_store=FileSecretStore())

    assert service.has_secret("gemini") is False


def test_has_secret_true_after_set_secret():
    store = FileSecretStore()
    service = SetupService(secret_store=store)

    service.set_secret("gemini", "super-secret")

    assert service.has_secret("gemini") is True
