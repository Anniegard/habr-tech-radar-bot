from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from habr_tech_radar.models.article import Article, FilterResult
from habr_tech_radar.scoring.heuristic import HeuristicArticleScoring
from habr_tech_radar.settings import Settings


def _article(
    *,
    title: str,
    summary: str | None = None,
    categories: list[str] | None = None,
    published_at: datetime | None = None,
) -> Article:
    meta: dict[str, Any] = {}
    if categories is not None:
        meta["categories"] = categories
    return Article.model_validate(
        {
            "id": "s1",
            "title": title,
            "url": "https://habr.com/ru/post/1/",
            "published_at": published_at or datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC),
            "summary": summary,
            "metadata": meta,
        }
    )


def test_scoring_keyword_title_and_summary_affect_points() -> None:
    settings = Settings(
        include_keywords="python",
        score_weight_include_keyword=5,
        score_weight_title_match_bonus=3,
        score_weight_recency_max=0,
        score_recency_window_days=14,
    )
    scorer = HeuristicArticleScoring(
        settings,
        reference_time=datetime(2026, 4, 10, tzinfo=UTC),
    )
    fr = FilterResult(
        article=_article(title="python asyncio", summary="discussion"),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.breakdown.get("include_keywords", 0) == 5
    assert score.explanation.breakdown.get("title_match_bonus", 0) == 3
    assert score.points == 8


def test_scoring_hub_match_in_categories() -> None:
    settings = Settings(
        include_hubs="Python",
        score_weight_include_hub=8,
        score_weight_recency_max=0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=datetime(2026, 4, 1, tzinfo=UTC))
    fr = FilterResult(
        article=_article(
            title="Other",
            summary="x",
            categories=["Программирование / Python"],
        ),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert "Python" in score.explanation.matched_include_hubs
    assert score.explanation.breakdown.get("include_hubs") == 8


def test_scoring_recency_uses_injected_reference_time() -> None:
    settings = Settings(
        score_weight_recency_max=10,
        score_recency_window_days=10.0,
    )
    ref = datetime(2026, 4, 10, tzinfo=UTC)
    old = ref - timedelta(days=10)
    scorer = HeuristicArticleScoring(settings, reference_time=ref)
    fr = FilterResult(article=_article(title="t", published_at=old), passed=True)
    score = scorer.score([fr])[0]
    assert score.explanation.breakdown.get("recency") == 0

    fresh = ref - timedelta(days=2)
    fr2 = FilterResult(article=_article(title="t2", published_at=fresh), passed=True)
    score2 = scorer.score([fr2])[0]
    assert score2.explanation.breakdown.get("recency", 0) > 0
