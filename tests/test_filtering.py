from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from habr_tech_radar.filtering.heuristic import HeuristicArticleFilter
from habr_tech_radar.models.article import Article
from habr_tech_radar.settings import Settings


def _art(
    *,
    article_id: str = "a1",
    title: str = "Hello",
    summary: str | None = None,
    categories: list[str] | None = None,
) -> Article:
    meta: dict[str, Any] = {}
    if categories is not None:
        meta["categories"] = categories
    return Article.model_validate(
        {
            "id": article_id,
            "title": title,
            "url": "https://habr.com/ru/post/1/",
            "published_at": datetime(2026, 1, 1, tzinfo=UTC),
            "summary": summary,
            "metadata": meta,
        }
    )


def test_filter_include_keyword_admits_match() -> None:
    f = HeuristicArticleFilter(
        Settings(include_keywords="python"),
    )
    results = f.filter([_art(title="Python tips", summary="other")])
    assert len(results) == 1
    assert results[0].passed is True


def test_filter_include_keyword_rejects_when_no_match() -> None:
    f = HeuristicArticleFilter(
        Settings(include_keywords="python"),
    )
    results = f.filter([_art(title="Rust tips", summary="nothing here")])
    assert len(results) == 1
    assert results[0].passed is False


def test_filter_exclude_keyword_rejects_immediately() -> None:
    f = HeuristicArticleFilter(
        Settings(include_keywords="python", exclude_keywords="spam"),
    )
    results = f.filter([_art(title="python spam", summary="x")])
    assert results[0].passed is False
    assert "exclude" in (results[0].reason or "").lower()
