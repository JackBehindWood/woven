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
    config_dir,
    config_path,
    load_config,
    resolve_api_key,
)


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
        model_providers: dict[str, type[Model]] = MODEL_PROVIDERS,
    ) -> None:
        self._secret_store = secret_store or FileSecretStore()
        self._load_config = load_config
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
            if resolve_api_key(self._secret_store, provider) is not None:
                checks.append(
                    DiagnosticCheck(
                        name=f"credentials:{provider}",
                        status=CheckStatus.OK,
                        message=f"API key configured for {provider}.",
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

    def run_all(self) -> list[DiagnosticCheck]:
        checks: list[DiagnosticCheck] = [
            self.check_environment(),
            self.check_dependencies(),
        ]
        checks.extend(self.check_config_validity())
        checks.extend(self.check_credentials())
        checks.append(self.check_provider_reachable())
        return checks
