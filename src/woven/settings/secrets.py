from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from woven.settings.store import config_dir

PROVIDER_ENV_VARS: dict[str, str] = {"gemini": "GEMINI_API_KEY"}

_SECRETS_FILE_MODE = 0o600
_SECRETS_DIR_MODE = 0o700


class SecretStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...

    def delete(self, key: str) -> None: ...


def secrets_path() -> Path:
    return config_dir() / "secrets.json"


class FileSecretStore:
    """Secrets, physically separate from `config.json`'s ordinary settings."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or secrets_path()

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        data: dict[str, str] = json.loads(self._path.read_text() or "{}")
        if (self._path.stat().st_mode & 0o777) != _SECRETS_FILE_MODE:
            self._path.chmod(_SECRETS_FILE_MODE)
        return data

    def _save(self, data: dict[str, str]) -> None:
        directory = self._path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=_SECRETS_DIR_MODE)
        directory.chmod(_SECRETS_DIR_MODE)
        payload = json.dumps(data, indent=2).encode()
        fd = os.open(
            self._path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, _SECRETS_FILE_MODE
        )
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        self._path.chmod(_SECRETS_FILE_MODE)

    def get(self, key: str) -> str | None:
        return self._load().get(key)

    def set(self, key: str, value: str) -> None:
        data = self._load()
        data[key] = value
        self._save(data)

    def delete(self, key: str) -> None:
        data = self._load()
        data.pop(key, None)
        self._save(data)


def resolve_api_key_with_source(
    store: SecretStore, provider: str
) -> tuple[str, str] | None:
    env_var = PROVIDER_ENV_VARS.get(provider)
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value, "env"
    file_value = store.get(f"{provider}_api_key")
    if file_value is not None:
        return file_value, "file"
    return None


def resolve_api_key(store: SecretStore, provider: str) -> str | None:
    resolved = resolve_api_key_with_source(store, provider)
    return resolved[0] if resolved is not None else None
