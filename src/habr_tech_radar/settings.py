from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_HABR_RSS_URLS: tuple[str, ...] = ("https://habr.com/ru/rss/articles/",)

# Built-in scoring lexicons (comma-separated defaults; override via HTR_SCORE_*_KEYWORDS).
_DEFAULT_SCORE_STRONG_KEYWORDS: str = (
    "LLM,RAG,MCP,LangChain,OpenAI API,OpenAI,vector db,vector database,embedding,"
    "embeddings,inference,fine-tuning,fine tuning,prompt engineering,function calling,"
    "retrieval,benchmark,evaluation,production pipeline,pipeline,FastAPI,gRPC,asyncio,"
    "REST API,GraphQL,WebSocket,microservices,microservice,pytest,typing,LangGraph,"
    "agent framework,AI agent,инференс,дообучение,эмбеддинг,микросервис,бэкенд"
)
_DEFAULT_SCORE_TECHNICAL_KEYWORDS: str = (
    "Kubernetes,Docker,PostgreSQL,Redis,CI/CD,observability,tracing,Prometheus,"
    "GitHub Actions,Terraform,nginx,kafka,messaging,backend,distributed system,"
    "race condition,memory leak,profiling,latency,SRE,DevOps,мониторинг,контейнер"
)
_DEFAULT_SCORE_NEGATIVE_KEYWORDS: str = (
    "smart home,умный дом,гаджет,обзор смартфона,топ-10,топ 10,шокирующ,кликбейт,"
    "своими руками,DIY без,спонсор поста,sponsored,честный обзор,лучшие подборки,"
    "умная колонка,робот-пылесос,кухонный комбайн,фитнес-браслет"
)


def parse_comma_separated_list(v: object) -> list[str]:
    """Parse env list: comma/whitespace separated, strip, drop empties."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        parts = re.split(r"[\s,]+", s)
        return [p for p in parts if p]
    return []


class Settings(BaseSettings):
    """Application configuration from environment and optional `.env` file."""

    model_config = SettingsConfigDict(
        env_prefix="HTR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO", description="Logging level name")
    dry_run: bool = Field(
        default=True,
        description="If true, do not call Telegram API (messages logged as would-send HTML)",
    )
    demo_mode: bool = Field(
        default=False,
        description="When true, ingest one synthetic article (no network)",
    )

    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)
    telegram_send_max_attempts: int = Field(
        default=4,
        ge=1,
        le=10,
        description="sendMessage attempts per article (includes first try; retries = N-1)",
    )
    telegram_retry_base_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay for exponential backoff between transient Telegram failures",
    )
    telegram_max_delivery_seconds: float = Field(
        default=240.0,
        ge=1.0,
        le=3600.0,
        description="Monotonic time budget for the Telegram delivery phase (live and dry_run)",
    )
    telegram_format_mode: str = Field(
        default="prod",
        description="Telegram HTML layout: prod (compact) or debug (full score breakdown)",
    )
    last_run_path: Path = Field(
        default=Path(".runtime/last_run.json"),
        description="JSON snapshot of the last pipeline run (atomic write)",
    )
    health_max_age_minutes: float = Field(
        default=180.0,
        ge=1.0,
        description="Health: max age (minutes) of finished_at_utc for a fresh last_run",
    )
    openai_api_key: str | None = Field(default=None)

    project_root: Path | None = Field(
        default=None,
        description="If set, relative HTR_STATE_FILE is resolved under this directory (not cwd)",
    )

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

    include_keywords: str = Field(
        default="",
        description="Comma/whitespace-separated; if non-empty, OR-gate with include_hubs",
    )
    exclude_keywords: str = Field(
        default="",
        description="Comma/whitespace-separated; reject if any term matches",
    )
    include_hubs: str = Field(
        default="",
        description="Comma/whitespace-separated hub/category substrings",
    )
    exclude_hubs: str = Field(
        default="",
        description="Comma/whitespace-separated; reject on category/text match",
    )
    max_selected_articles: int = Field(
        default=20,
        ge=1,
        description="Top N articles after scoring (per run)",
    )

    score_weight_include_keyword: int = Field(
        default=5,
        ge=0,
        description="Points per include keyword hit",
    )
    score_weight_strong_keyword: int = Field(
        default=12,
        ge=0,
        description="Points per strong/high-signal keyword hit",
    )
    score_weight_technical_signal: int = Field(
        default=10,
        ge=0,
        description="Points per technical/contextual keyword hit",
    )
    score_weight_penalty_per_hit: int = Field(
        default=4,
        ge=0,
        description="Points subtracted per negative/noise keyword hit",
    )
    score_weight_include_hub: int = Field(default=8, ge=0, description="Points per include hub hit")
    score_weight_title_match_bonus: int = Field(
        default=3,
        ge=0,
        description=(
            "Extra points when a scored keyword (include/strong/technical) appears in the title"
        ),
    )
    score_strong_keywords: str = Field(
        default=_DEFAULT_SCORE_STRONG_KEYWORDS,
        description="Comma-separated strong signals for scoring (substring, case-insensitive)",
    )
    score_technical_keywords: str = Field(
        default=_DEFAULT_SCORE_TECHNICAL_KEYWORDS,
        description="Comma-separated technical signals for scoring",
    )
    score_negative_keywords: str = Field(
        default=_DEFAULT_SCORE_NEGATIVE_KEYWORDS,
        description="Comma-separated noise indicators (penalty per hit)",
    )
    score_weight_recency_max: int = Field(
        default=4,
        ge=0,
        description=(
            "Max recency bonus (linear decay over the window). Env: HTR_SCORE_WEIGHT_RECENCY_MAX"
        ),
    )
    score_recency_max_points: int | None = Field(
        default=None,
        ge=0,
        description=(
            "If set, overrides score_weight_recency_max (env: HTR_SCORE_RECENCY_MAX_POINTS)"
        ),
    )
    score_recency_window_days: float = Field(
        default=14.0,
        ge=0.1,
        description="Age in days at which recency bonus reaches zero",
    )

    @field_validator("log_level")
    @classmethod
    def log_level_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("telegram_format_mode", mode="before")
    @classmethod
    def telegram_format_mode_norm(cls, v: object) -> str:
        if v is None:
            return "prod"
        s = str(v).strip().casefold()
        if s in ("prod", "production"):
            return "prod"
        if s in ("debug", "dev", "development"):
            return "debug"
        raise ValueError("HTR_TELEGRAM_FORMAT_MODE must be prod or debug")

    @field_validator("score_recency_max_points", mode="before")
    @classmethod
    def empty_recency_override_to_none(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

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

    @field_validator("last_run_path", mode="before")
    @classmethod
    def last_run_path_path(cls, v: object) -> Path:
        if isinstance(v, Path):
            return v
        return Path(str(v))

    @field_validator("project_root", mode="before")
    @classmethod
    def project_root_path(cls, v: object) -> Path | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return Path(s)


def effective_state_file(settings: Settings) -> Path:
    """Resolve HTR_STATE_FILE for persistence.

    Absolute paths are unchanged; relative paths use cwd or HTR_PROJECT_ROOT.
    """
    p = settings.state_file
    if p.is_absolute():
        return p.resolve()
    if settings.project_root is not None:
        return (settings.project_root / p).resolve()
    return (Path.cwd() / p).resolve()


def effective_last_run_path(settings: Settings) -> Path:
    """Resolve HTR_LAST_RUN_PATH for persistence (same rules as HTR_STATE_FILE)."""
    p = settings.last_run_path
    if p.is_absolute():
        return p.resolve()
    if settings.project_root is not None:
        return (settings.project_root / p).resolve()
    return (Path.cwd() / p).resolve()


def effective_recency_max_points(settings: Settings) -> int:
    """Max recency bonus: HTR_SCORE_RECENCY_MAX_POINTS overrides HTR_SCORE_WEIGHT_RECENCY_MAX."""
    if settings.score_recency_max_points is not None:
        return settings.score_recency_max_points
    return settings.score_weight_recency_max
