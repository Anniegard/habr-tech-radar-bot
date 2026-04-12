from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_HABR_RSS_URLS: tuple[str, ...] = ("https://habr.com/ru/rss/articles/",)


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

    habr_rss_urls: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_HABR_RSS_URLS),
        description="Comma- or newline-separated Habr RSS feed URLs",
    )
    state_file: Path = Field(
        default=Path(".habr_tech_radar_seen.json"),
        description="JSON file storing seen article IDs between runs",
    )
    rss_fetch_timeout_seconds: float = Field(
        default=30.0,
        ge=0.1,
        le=300.0,
        description="HTTP timeout for each RSS request",
    )

    @field_validator("log_level")
    @classmethod
    def log_level_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("habr_rss_urls", mode="before")
    @classmethod
    def normalize_habr_rss_urls(cls, v: object) -> list[str]:
        if v is None:
            return list(_DEFAULT_HABR_RSS_URLS)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            parts = re.split(r"[\s,]+", s)
            return [p for p in parts if p]
        return list(_DEFAULT_HABR_RSS_URLS)

    @field_validator("state_file", mode="before")
    @classmethod
    def state_file_path(cls, v: object) -> Path:
        if isinstance(v, Path):
            return v
        return Path(str(v))
