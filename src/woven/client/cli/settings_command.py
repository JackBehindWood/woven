from __future__ import annotations

import typer

from woven.client.cli.console import make_console
from woven.client.cli.registry import register_group
from woven.client.cli.render import render_error, render_status_panel
from woven.settings import (
    PROVIDER_ENV_VARS,
    ConfigError,
    FileSecretStore,
    load_config,
    resolve_api_key,
    save_config,
)
from woven.setup.fields import FIELDS

settings_app = register_group("settings")(
    typer.Typer(
        name="settings",
        help="Show or persist Woven's default settings.",
        add_completion=False,
    )
)

# cli field name -> secret key in the SecretStore, one per known provider.
_SECRET_FIELDS: dict[str, str] = {
    f"{provider}-api-key": f"{provider}_api_key" for provider in PROVIDER_ENV_VARS
}

_ALL_FIELD_NAMES = sorted({*FIELDS, *_SECRET_FIELDS})


@settings_app.command("show")
def show() -> None:
    """Show the persisted user and settings."""
    console = make_console()
    try:
        config = load_config()
    except ConfigError as exc:
        render_error(console, str(exc))
        raise typer.Exit(code=1) from None

    settings = config.settings
    store = FileSecretStore()
    lines = [
        f"user: {config.user.name} ({config.user.id})",
        f"default mode: {settings.default_mode}",
        f"default permission: {settings.default_permission_mode}",
        f"default model provider: {settings.default_model_provider or '(none)'}",
    ]
    for provider in sorted(PROVIDER_ENV_VARS):
        status = "set" if resolve_api_key(store, provider) else "not set"
        lines.append(f"{provider} api key: {status}")
    render_status_panel(console, "settings", lines)


@settings_app.command("set")
def set_field(
    field: str = typer.Argument(help="Setting to change."),
    value: str | None = typer.Argument(
        None, help="New value for the setting. Omit for a secret field to be prompted."
    ),
) -> None:
    """Persist a new value for one setting."""
    console = make_console()

    if field in _SECRET_FIELDS:
        if value is None:
            value = typer.prompt(f"Enter value for {field}", hide_input=True)
        FileSecretStore().set(_SECRET_FIELDS[field], value)
        render_status_panel(console, "settings", [f"{field} set to: (hidden)"])
        return

    entry = FIELDS.get(field)
    if entry is None:
        render_error(
            console,
            f"Unknown setting: {field}. Available: {', '.join(_ALL_FIELD_NAMES)}",
        )
        raise typer.Exit(code=1)

    if value is None:
        render_error(console, f"Value is required for {field}.")
        raise typer.Exit(code=1)

    attr, validator = entry
    error = validator(value)
    if error is not None:
        render_error(console, error)
        raise typer.Exit(code=1)

    try:
        config = load_config()
    except ConfigError as exc:
        render_error(console, str(exc))
        raise typer.Exit(code=1) from None

    new_settings = config.settings.model_copy(update={attr: value})
    new_config = config.model_copy(update={"settings": new_settings})
    save_config(new_config)

    render_status_panel(console, "settings", [f"{field} set to: {value}"])
