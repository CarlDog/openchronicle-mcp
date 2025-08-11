from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class AppSettings(BaseSettings):
    """Central application settings loaded from environment and .env."""

    env: str = "dev"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPENCHRONICLE_",
        extra="ignore",
    )
