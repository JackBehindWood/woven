from __future__ import annotations

from collections.abc import Callable


def validate_mode(value: str) -> str | None:
    from woven.modes import BUILTIN_MODES

    if value not in BUILTIN_MODES:
        return f"Unknown mode: {value}. Available: {', '.join(sorted(BUILTIN_MODES))}"
    return None


def validate_permission_mode(value: str) -> str | None:
    from woven.permissions import PERMISSION_MODES

    if value not in PERMISSION_MODES:
        return (
            f"Unknown permission mode: {value}. "
            f"Available: {', '.join(PERMISSION_MODES)}"
        )
    return None


def validate_model_provider(value: str) -> str | None:
    from woven.models import MODEL_PROVIDERS

    if value not in MODEL_PROVIDERS:
        return (
            f"Unknown model provider: {value}. "
            f"Available: {', '.join(sorted(MODEL_PROVIDERS))}"
        )
    return None


# field name -> (Settings attribute, validator). Single source of truth for
# both `woven settings set` and `woven setup`.
FIELDS: dict[str, tuple[str, Callable[[str], str | None]]] = {
    "mode": ("default_mode", validate_mode),
    "permission-mode": ("default_permission_mode", validate_permission_mode),
    "model-provider": ("default_model_provider", validate_model_provider),
}
