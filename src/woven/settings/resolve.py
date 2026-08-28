from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from woven.settings.models import Config


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str
    permission_mode: str
    model_provider: str | None = None


def resolve_runtime_config(
    config: Config,
    *,
    mode: str | None = None,
    permission_mode: str | None = None,
    model_provider: str | None = None,
) -> RuntimeConfig:
    """Merge CLI overrides onto persisted settings (CLI > persisted > default)."""
    return RuntimeConfig(
        mode=mode or config.settings.default_mode,
        permission_mode=permission_mode or config.settings.default_permission_mode,
        model_provider=model_provider or config.settings.default_model_provider,
    )
