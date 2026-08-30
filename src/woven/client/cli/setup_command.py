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
from woven.settings import PROVIDER_ENV_VARS
from woven.setup import CLEAR_SENTINEL, SetupError, SetupService

_MAX_KEY_ATTEMPTS = 3


def _current_settings_lines(service: SetupService) -> list[str]:
    settings = service.current_config().settings
    lines = [
        f"default mode: {settings.default_mode}",
        f"default permission: {settings.default_permission_mode}",
        f"default model provider: {settings.default_model_provider or '(none)'}",
    ]
    for provider in sorted(PROVIDER_ENV_VARS):
        status = "set" if service.has_secret(provider) else "not set"
        lines.append(f"{provider} api key: {status}")
    return lines


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


def _verify_connection(
    console: Console, provider: str, provider_cls: type, api_key: str
) -> bool:
    try:
        provider_cls(api_key=api_key).check_connection()
    except ModelError as exc:
        render_error(console, str(exc))
        return False
    render_status_panel(console, "setup", [f"{provider} connection verified."])
    return True


def _prompt_provider_and_key(console: Console, service: SetupService) -> None:
    available = ", ".join(sorted(MODEL_PROVIDERS))
    current = service.current_config().settings.default_model_provider or ""
    provider = typer.prompt(
        f"Default model provider ({available}; leave blank to keep current, "
        f"{CLEAR_SENTINEL!r} to clear)",
        default=current,
    ).strip()

    if not provider:
        return

    if provider == CLEAR_SENTINEL:
        try:
            service.set_field("model-provider", provider)
        except SetupError as exc:
            render_error(console, str(exc))
            return
        render_status_panel(console, "setup", ["model provider cleared."])
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
        if _verify_connection(console, provider, provider_cls, api_key):
            return
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


def _run_non_interactive(
    console: Console,
    service: SetupService,
    *,
    provider: str | None,
    api_key: str | None,
    mode: str | None,
    permission_mode: str | None,
) -> None:
    if api_key is not None and provider is None:
        render_error(console, "--api-key requires --provider.")
        raise typer.Exit(code=1)

    if provider is not None:
        try:
            service.set_field("model-provider", provider)
        except SetupError as exc:
            render_error(console, str(exc))
            raise typer.Exit(code=1) from None

        if provider != CLEAR_SENTINEL:
            if api_key is None:
                render_error(console, f"--api-key is required to configure {provider}.")
                raise typer.Exit(code=1)
            service.set_secret(provider, api_key)
            provider_cls = MODEL_PROVIDERS[provider]
            if not _verify_connection(console, provider, provider_cls, api_key):
                raise typer.Exit(code=1)

    for field, value in (("mode", mode), ("permission-mode", permission_mode)):
        if value is None:
            continue
        try:
            service.set_field(field, value)
        except SetupError as exc:
            render_error(console, str(exc))
            raise typer.Exit(code=1) from None

    render_status_panel(console, "current settings", _current_settings_lines(service))


@register_command("setup")
def setup_command(
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Model provider to configure (non-interactive mode only).",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key for --provider (non-interactive mode only).",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Default mode to persist (non-interactive mode only).",
    ),
    permission_mode: str | None = typer.Option(
        None,
        "--permission-mode",
        help="Default permission tier to persist (non-interactive mode only).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Skip every prompt; fail loudly on a missing required value instead of "
        "asking for it. For CI/onboarding scripts.",
    ),
) -> None:
    """Guided, interactive configuration for Woven's defaults."""
    console = make_console()
    service = SetupService()

    if non_interactive:
        _run_non_interactive(
            console,
            service,
            provider=provider,
            api_key=api_key,
            mode=mode,
            permission_mode=permission_mode,
        )
        return

    render_status_panel(console, "current settings", _current_settings_lines(service))

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
