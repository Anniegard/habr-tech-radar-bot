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


class ScoreExplanation(BaseModel):
    """Deterministic breakdown for debugging and future Telegram formatting."""

    matched_include_keywords: list[str] = Field(default_factory=list)
    matched_exclude_keywords: list[str] = Field(default_factory=list)
    matched_strong_keywords: list[str] = Field(default_factory=list)
    matched_technical_keywords: list[str] = Field(default_factory=list)
    matched_negative_keywords: list[str] = Field(default_factory=list)
    matched_include_hubs: list[str] = Field(default_factory=list)
    breakdown: dict[str, int] = Field(default_factory=dict)
    selection_summary: str | None = Field(
        default=None,
        description="Short human-facing 'why selected' line (strong/tech/include signals)",
    )


class ArticleScore(BaseModel):
    """Integer relevance score with structured explanation."""

    article: Article
    points: int = Field(description="Deterministic relevance score (higher is better)")
    explanation: ScoreExplanation = Field(default_factory=ScoreExplanation)
    reasons: list[str] = Field(
        default_factory=list,
        description="Short human-readable lines (optional; mirrors explanation)",
    )


class RadarItem(BaseModel):
    """Article ready for delivery after scoring (and optional enrichment)."""

    score: ArticleScore
    enriched_summary: str | None = None
