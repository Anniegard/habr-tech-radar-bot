from __future__ import annotations

from datetime import UTC, datetime

from habr_tech_radar.models.article import ArticleScore


def _published_timestamp(published_at: datetime) -> float:
    dt = published_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).timestamp()


def select_top_scored(scores: list[ArticleScore], limit: int) -> list[ArticleScore]:
    """Sort by points desc, then newer published_at, then id asc; return first `limit` items."""
    if limit < 1:
        msg = "limit must be >= 1"
        raise ValueError(msg)
    ordered = sorted(
        scores,
        key=lambda s: (
            -s.points,
            -_published_timestamp(s.article.published_at),
            s.article.id,
        ),
    )
    return ordered[:limit]
