from __future__ import annotations

from collections.abc import Iterable

import typer
from rich.console import Console

from woven.client.cli.console import make_console
from woven.client.cli.registry import register_command
from woven.client.cli.render import (
    render_diagnostics,
    render_error,
    render_status_panel,
)
from woven.diagnostics import DiagnosticService
from woven.models import MODEL_PROVIDERS, ModelError
from woven.modes import BUILTIN_MODES
from woven.permissions import PERMISSION_MODES
from woven.settings import Config
from woven.setup import SetupError, SetupService

_MAX_KEY_ATTEMPTS = 3


def _current_settings_lines(config: Config) -> list[str]:
    settings = config.settings
    return [
        f"default mode: {settings.default_mode}",
        f"default permission: {settings.default_permission_mode}",
        f"default model provider: {settings.default_model_provider or '(none)'}",
    ]


def _prompt_field(
    console: Console,
    service: SetupService,
    field: str,
    label: str,
    choices: Iterable[str],
    current: str,
) -> None:
    available = ", ".join(sorted(choices))
    while True:
        value = typer.prompt(f"{label} ({available})", default=current)
        try:
            service.set_field(field, value)
        except SetupError as exc:
            render_error(console, str(exc))
            continue
        return


def _prompt_provider_and_key(console: Console, service: SetupService) -> None:
    available = ", ".join(sorted(MODEL_PROVIDERS))
    current = service.current_config().settings.default_model_provider or ""
    provider = typer.prompt(
        f"Default model provider ({available}; leave blank to skip)",
        default=current,
    ).strip()

    if not provider:
        return

    try:
        service.set_field("model-provider", provider)
    except SetupError as exc:
        render_error(console, str(exc))
        return

    provider_cls = MODEL_PROVIDERS[provider]
    console.print(f"[woven.dim]{provider_cls.SETUP_HINT}[/woven.dim]")

    for attempt in range(1, _MAX_KEY_ATTEMPTS + 1):
        api_key = typer.prompt(f"Enter {provider} API key", hide_input=True)
        service.set_secret(provider, api_key)
        try:
            provider_cls(api_key=api_key).check_connection()
        except ModelError as exc:
            render_error(console, str(exc))
            if attempt == _MAX_KEY_ATTEMPTS:
                render_status_panel(
                    console,
                    "setup",
                    [
                        (
                            f"Could not verify the {provider} API key after "
                            f"{_MAX_KEY_ATTEMPTS} attempts. Re-run `woven setup` "
                            "later to fix it."
                        )
                    ],
                )
            continue
        render_status_panel(console, "setup", [f"{provider} connection verified."])
        return


@register_command("setup")
def setup_command() -> None:
    """Guided, interactive configuration for Woven's defaults."""
    console = make_console()
    service = SetupService()

    config = service.current_config()
    render_status_panel(console, "current settings", _current_settings_lines(config))

    _prompt_provider_and_key(console, service)

    config = service.current_config()
    _prompt_field(
        console,
        service,
        "mode",
        "Default mode",
        BUILTIN_MODES,
        config.settings.default_mode,
    )

    config = service.current_config()
    _prompt_field(
        console,
        service,
        "permission-mode",
        "Default permission tier",
        PERMISSION_MODES,
        config.settings.default_permission_mode,
    )

    if typer.confirm(
        "Run `woven doctor` now to verify everything end-to-end?", default=True
    ):
        checks = DiagnosticService().run_all()
        render_diagnostics(console, checks)
