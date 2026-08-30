from __future__ import annotations

from collections.abc import Callable

from woven.settings import (
    PROVIDER_ENV_VARS,
    Config,
    FileSecretStore,
    SecretStore,
    load_config,
    resolve_api_key,
    save_config,
)
from woven.setup.fields import FIELDS, coerce_value


class SetupError(Exception):
    """Raised when a guided-setup field or secret cannot be persisted."""


class SetupService:
    def __init__(
        self,
        *,
        secret_store: SecretStore | None = None,
        load_config: Callable[[], Config] = load_config,
        save_config: Callable[[Config], None] = save_config,
    ) -> None:
        self._secret_store = secret_store or FileSecretStore()
        self._load_config = load_config
        self._save_config = save_config

    def current_config(self) -> Config:
        return self._load_config()

    def set_field(self, field: str, value: str) -> Config:
        entry = FIELDS.get(field)
        if entry is None:
            raise SetupError(
                f"Unknown setting: {field}. Available: {', '.join(sorted(FIELDS))}"
            )
        attr, validator = entry
        error = validator(value)
        if error is not None:
            raise SetupError(error)

        config = self._load_config()
        new_settings = config.settings.model_copy(
            update={attr: coerce_value(field, value)}
        )
        new_config = config.model_copy(update={"settings": new_settings})
        self._save_config(new_config)
        return new_config

    def set_secret(self, provider: str, value: str) -> None:
        if provider not in PROVIDER_ENV_VARS:
            raise SetupError(
                f"Unknown model provider: {provider}. "
                f"Available: {', '.join(sorted(PROVIDER_ENV_VARS))}"
            )
        self._secret_store.set(f"{provider}_api_key", value)

    def has_secret(self, provider: str) -> bool:
        return resolve_api_key(self._secret_store, provider) is not None
