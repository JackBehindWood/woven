from __future__ import annotations

from collections.abc import Callable

# Sentinel value for `set_field("model-provider", ...)` that clears the
# configured provider back to `None` (FakeModel). There's otherwise no way
# back once a provider is set, since an empty string fails validation.
CLEAR_SENTINEL = "none"


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

    if value == CLEAR_SENTINEL:
        return None
    if value not in MODEL_PROVIDERS:
        return (
            f"Unknown model provider: {value}. "
            f"Available: {', '.join(sorted(MODEL_PROVIDERS))}, {CLEAR_SENTINEL!r} "
            "(clear)"
        )
    return None


def coerce_value(field: str, value: str) -> str | None:
    """Translate a validated raw value into what actually gets persisted.

    Only `model-provider`'s clear sentinel needs this today: it validates as
    a plain string but must persist as `None`. Every other field passes
    through unchanged.
    """
    if field == "model-provider" and value == CLEAR_SENTINEL:
        return None
    return value


# field name -> (Settings attribute, validator). Single source of truth for
# both `woven settings set` and `woven setup`.
FIELDS: dict[str, tuple[str, Callable[[str], str | None]]] = {
    "mode": ("default_mode", validate_mode),
    "permission-mode": ("default_permission_mode", validate_permission_mode),
    "model-provider": ("default_model_provider", validate_model_provider),
}
