from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from woven.models import MODEL_PROVIDERS, Model, ModelError
from woven.modes import BUILTIN_MODES
from woven.permissions import PERMISSION_MODES
from woven.settings import (
    PROVIDER_ENV_VARS,
    Config,
    FileSecretStore,
    SecretStore,
    Settings,
    config_dir,
    config_path,
    load_config,
    resolve_api_key,
    resolve_api_key_with_source,
    save_config,
)
from woven.setup import CLEAR_SENTINEL, SetupService

_SOURCE_LABELS = {"env": "environment variable", "file": "secrets file"}

# `check_config_validity`'s WARN check name -> (`FIELDS` key, safe default).
# Pulled from `Settings`'s own field defaults so they can't drift out of sync
# with `woven.settings.models`. Only these three are "safely auto-correctable"
# — never `credentials:*`/`provider`, which need a real key or network call.
_FIXABLE_CONFIG_CHECKS: dict[str, tuple[str, str]] = {
    "config:mode": ("mode", Settings.model_fields["default_mode"].default),
    "config:permission-mode": (
        "permission-mode",
        Settings.model_fields["default_permission_mode"].default,
    ),
    "config:model-provider": ("model-provider", CLEAR_SENTINEL),
}


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: CheckStatus
    message: str
    fix_hint: str | None = None


class DiagnosticService:
    def __init__(
        self,
        *,
        secret_store: SecretStore | None = None,
        load_config: Callable[[], Config] = load_config,
        save_config: Callable[[Config], None] = save_config,
        model_providers: dict[str, type[Model]] = MODEL_PROVIDERS,
    ) -> None:
        self._secret_store = secret_store or FileSecretStore()
        self._load_config = load_config
        self._save_config = save_config
        self._model_providers = model_providers

    def check_environment(self) -> DiagnosticCheck:
        try:
            self._load_config()
        except Exception as exc:  # noqa: BLE001 - surface as a failed check, not a crash
            return DiagnosticCheck(
                name="environment",
                status=CheckStatus.FAIL,
                message=f"Config could not be loaded: {exc}",
                fix_hint="Check the config file's contents or delete it to reset.",
            )

        directory = config_dir()
        path = config_path()
        problems: list[str] = []
        dir_mode = directory.stat().st_mode & 0o777
        if dir_mode != 0o700:
            problems.append(f"config dir has mode {oct(dir_mode)}, expected 0o700")
        file_mode = path.stat().st_mode & 0o777
        if file_mode != 0o600:
            problems.append(f"config file has mode {oct(file_mode)}, expected 0o600")

        if problems:
            return DiagnosticCheck(
                name="environment",
                status=CheckStatus.FAIL,
                message="; ".join(problems),
                fix_hint=f"Fix permissions on {directory} and {path}.",
            )
        return DiagnosticCheck(
            name="environment",
            status=CheckStatus.OK,
            message=f"Config at {path} is readable and writable.",
        )

    def check_dependencies(self) -> DiagnosticCheck:
        try:
            import google.genai  # noqa: F401
        except ImportError as exc:
            return DiagnosticCheck(
                name="dependencies",
                status=CheckStatus.FAIL,
                message=f"Missing dependency: {exc}",
                fix_hint="Run `uv sync` to install missing dependencies.",
            )
        return DiagnosticCheck(
            name="dependencies",
            status=CheckStatus.OK,
            message="Required dependencies are installed.",
        )

    def check_config_validity(self) -> list[DiagnosticCheck]:
        config = self._load_config()
        settings = config.settings
        checks: list[DiagnosticCheck] = []

        if settings.default_mode in BUILTIN_MODES:
            checks.append(
                DiagnosticCheck(
                    name="config:mode",
                    status=CheckStatus.OK,
                    message=f"Default mode is '{settings.default_mode}'.",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    name="config:mode",
                    status=CheckStatus.WARN,
                    message=f"Default mode '{settings.default_mode}' is no longer "
                    "a known mode.",
                    fix_hint="Available: "
                    f"{', '.join(sorted(BUILTIN_MODES))}. "
                    "Run `woven settings set mode <value>`.",
                )
            )

        if settings.default_permission_mode in PERMISSION_MODES:
            checks.append(
                DiagnosticCheck(
                    name="config:permission-mode",
                    status=CheckStatus.OK,
                    message="Default permission mode is "
                    f"'{settings.default_permission_mode}'.",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    name="config:permission-mode",
                    status=CheckStatus.WARN,
                    message="Default permission mode "
                    f"'{settings.default_permission_mode}' is no longer known.",
                    fix_hint=f"Available: {', '.join(PERMISSION_MODES)}. "
                    "Run `woven settings set permission-mode <value>`.",
                )
            )

        provider = settings.default_model_provider
        if provider is None:
            checks.append(
                DiagnosticCheck(
                    name="config:model-provider",
                    status=CheckStatus.OK,
                    message="No default model provider configured.",
                )
            )
        elif provider in self._model_providers:
            checks.append(
                DiagnosticCheck(
                    name="config:model-provider",
                    status=CheckStatus.OK,
                    message=f"Default model provider is '{provider}'.",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    name="config:model-provider",
                    status=CheckStatus.WARN,
                    message=f"Default model provider '{provider}' is no longer known.",
                    fix_hint="Available: "
                    f"{', '.join(sorted(self._model_providers))}. "
                    "Run `woven settings set model-provider <value>`.",
                )
            )

        return checks

    def check_credentials(self) -> list[DiagnosticCheck]:
        checks: list[DiagnosticCheck] = []
        for provider in sorted(PROVIDER_ENV_VARS):
            resolved = resolve_api_key_with_source(self._secret_store, provider)
            if resolved is not None:
                _, source = resolved
                source_label = _SOURCE_LABELS[source]
                checks.append(
                    DiagnosticCheck(
                        name=f"credentials:{provider}",
                        status=CheckStatus.OK,
                        message=f"API key configured for {provider} "
                        f"(source: {source_label}).",
                    )
                )
                continue

            provider_cls = self._model_providers.get(provider)
            setup_hint = getattr(provider_cls, "SETUP_HINT", None)
            fix_hint = (
                f"{setup_hint} Then run `woven setup` or "
                f"`woven settings set {provider}-api-key`."
                if setup_hint
                else f"Run `woven setup` or `woven settings set {provider}-api-key`."
            )
            checks.append(
                DiagnosticCheck(
                    name=f"credentials:{provider}",
                    status=CheckStatus.WARN,
                    message=f"No API key configured for {provider}.",
                    fix_hint=fix_hint,
                )
            )
        return checks

    def check_provider_reachable(self) -> DiagnosticCheck:
        config = self._load_config()
        provider = config.settings.default_model_provider
        if provider is None:
            return DiagnosticCheck(
                name="provider",
                status=CheckStatus.WARN,
                message="No default model provider configured.",
                fix_hint="Run `woven setup` to choose one.",
            )

        api_key = resolve_api_key(self._secret_store, provider)
        if api_key is None:
            return DiagnosticCheck(
                name="provider",
                status=CheckStatus.FAIL,
                message=f"No API key configured for {provider}.",
                fix_hint=f"Run `woven settings set {provider}-api-key`.",
            )

        provider_cls = self._model_providers.get(provider)
        if provider_cls is None:
            return DiagnosticCheck(
                name="provider",
                status=CheckStatus.FAIL,
                message=f"Unknown model provider '{provider}' configured.",
                fix_hint="Run `woven settings set model-provider <value>` "
                "to pick a supported provider.",
            )

        try:
            model = provider_cls(api_key=api_key)
            model.check_connection()
        except ModelError as exc:
            return DiagnosticCheck(
                name="provider",
                status=CheckStatus.FAIL,
                message=f"{provider} is not reachable.",
                fix_hint=str(exc),
            )
        return DiagnosticCheck(
            name="provider",
            status=CheckStatus.OK,
            message=f"{provider} is reachable.",
        )

    def fix_config_validity(self) -> list[str]:
        """Reset any stale `config:*` field to its safe default. Returns one
        plain-text message per field actually changed."""
        service = SetupService(
            secret_store=self._secret_store,
            load_config=self._load_config,
            save_config=self._save_config,
        )
        messages: list[str] = []
        for check in self.check_config_validity():
            if check.status != CheckStatus.WARN:
                continue
            entry = _FIXABLE_CONFIG_CHECKS.get(check.name)
            if entry is None:
                continue
            field, safe_default = entry
            service.set_field(field, safe_default)
            if field == "model-provider":
                messages.append(f"{check.name}: cleared (was invalid).")
            else:
                messages.append(
                    f"{check.name}: reset to '{safe_default}' (was invalid)."
                )
        return messages

    def run_all(self) -> list[DiagnosticCheck]:
        checks: list[DiagnosticCheck] = [
            self.check_environment(),
            self.check_dependencies(),
        ]
        checks.extend(self.check_config_validity())
        checks.extend(self.check_credentials())
        checks.append(self.check_provider_reachable())
        return checks
