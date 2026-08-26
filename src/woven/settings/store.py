from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from woven.settings.models import Config, Settings, User

_CONFIG_FILE_MODE = 0o600
_CONFIG_DIR_MODE = 0o700

_LEGACY_GEMINI_API_KEY_FIELD = "gemini_api_key"


class ConfigError(Exception):
    """Raised when the persisted config file cannot be loaded."""


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "woven"


def config_path() -> Path:
    return config_dir() / "config.json"


def _default_config() -> Config:
    return Config(
        user=User(id=uuid.uuid4().hex, name="local"),
        settings=Settings(),
    )


def _migrate_legacy_gemini_api_key(raw_data: object, config: Config) -> Config:
    """One-time move of a pre-SecretStore `settings.gemini_api_key` value.

    Pydantic silently drops unknown keys, so a legacy key never breaks
    loading — but silently dropping a real secret is worse than migrating
    it, so this peeks the raw JSON (parsed separately from the model) before
    it is gone.
    """
    if not isinstance(raw_data, dict):
        return config
    legacy_value = raw_data.get("settings", {}).get(_LEGACY_GEMINI_API_KEY_FIELD)
    if not legacy_value:
        return config

    from woven.settings.secrets import FileSecretStore

    FileSecretStore().set("gemini_api_key", legacy_value)
    save_config(config)
    return config


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        config = _default_config()
        save_config(config)
        return config

    try:
        raw = path.read_text()
        raw_data = json.loads(raw)
        config = Config.model_validate(raw_data)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Failed to load config at {path}: {exc}") from exc

    if (path.stat().st_mode & 0o777) != _CONFIG_FILE_MODE:
        path.chmod(_CONFIG_FILE_MODE)

    return _migrate_legacy_gemini_api_key(raw_data, config)


def save_config(config: Config) -> None:
    path = config_path()
    try:
        directory = config_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=_CONFIG_DIR_MODE)
        directory.chmod(_CONFIG_DIR_MODE)
        payload = config.model_dump_json(indent=2).encode()
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, _CONFIG_FILE_MODE)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        # os.open's mode only applies to a newly-created file (subject to
        # umask); an already-existing file keeps its prior permissions, so
        # this chmod is what self-heals a loosened pre-existing file.
        path.chmod(_CONFIG_FILE_MODE)
    except OSError as exc:
        raise ConfigError(f"Failed to save config at {path}: {exc}") from exc
