from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    default_mode: str = "chat"
    default_permission_mode: str = "guarded"
    default_model_provider: str | None = None


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    user: User
    settings: Settings
