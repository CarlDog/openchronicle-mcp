"""Application settings loaded from environment and optional .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Central application settings."""

    env: str = "dev"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPENCHRONICLE_",
        extra="ignore",
    )
