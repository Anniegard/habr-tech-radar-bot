from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Article(BaseModel):
    """A Habr (or compatible) article reference."""

    id: str
    title: str
    url: HttpUrl
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FilterResult(BaseModel):
    """Outcome of filtering a single article."""

    article: Article
    passed: bool
    reason: str | None = None


class ArticleScore(BaseModel):
    """Numeric score with human-readable reasons."""

    article: Article
    value: float = Field(ge=0.0, le=1.0, description="Normalized score 0..1")
    reasons: list[str] = Field(default_factory=list)


class RadarItem(BaseModel):
    """Article ready for delivery after scoring (and optional enrichment)."""

    score: ArticleScore
    enriched_summary: str | None = None
