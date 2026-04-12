from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment and optional `.env` file."""

    model_config = SettingsConfigDict(
        env_prefix="HTR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO", description="Logging level name")
    dry_run: bool = Field(default=True, description="Avoid destructive or external side effects")
    demo_mode: bool = Field(
        default=False,
        description="When true, ingest one synthetic article (no network)",
    )

    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)

    @field_validator("log_level")
    @classmethod
    def log_level_upper(cls, v: str) -> str:
        return v.upper()
