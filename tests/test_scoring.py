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
        score_strong_keywords="",
        score_technical_keywords="",
        score_negative_keywords="",
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


def test_scoring_strong_signal_outscores_fresh_weak_include() -> None:
    """Older article with strong keyword beats very fresh include-only match."""
    ref = datetime(2026, 4, 10, tzinfo=UTC)
    settings = Settings(
        include_keywords="weakonly",
        score_strong_keywords="strongonly",
        score_technical_keywords="",
        score_negative_keywords="",
        score_weight_include_keyword=5,
        score_weight_strong_keyword=12,
        score_weight_title_match_bonus=3,
        score_weight_recency_max=4,
        score_recency_window_days=10.0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=ref)
    fresh_weak = FilterResult(
        article=_article(
            title="weakonly hype",
            summary="weakonly",
            published_at=ref,
        ),
        passed=True,
    )
    old_strong = FilterResult(
        article=_article(
            title="strongonly deep dive",
            summary="strongonly",
            published_at=ref - timedelta(days=10),
        ),
        passed=True,
    )
    s_weak = scorer.score([fresh_weak])[0]
    s_strong = scorer.score([old_strong])[0]
    assert s_strong.points > s_weak.points


def test_scoring_strong_keyword_weight_exceeds_include() -> None:
    settings = Settings(
        include_keywords="samekw",
        score_strong_keywords="samekw",
        score_technical_keywords="",
        score_negative_keywords="",
        score_weight_include_keyword=5,
        score_weight_strong_keyword=12,
        score_weight_title_match_bonus=0,
        score_weight_recency_max=0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=datetime(2026, 1, 1, tzinfo=UTC))
    fr = FilterResult(
        article=_article(title="other", summary="samekw in body"),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.matched_strong_keywords
    assert not score.explanation.matched_include_keywords
    assert score.explanation.breakdown.get("strong_keywords", 0) == 12


def test_scoring_penalties_reduce_score_and_points_floor() -> None:
    settings = Settings(
        include_keywords="tech",
        score_strong_keywords="",
        score_technical_keywords="",
        score_negative_keywords="noisebad",
        score_weight_include_keyword=10,
        score_weight_penalty_per_hit=6,
        score_weight_recency_max=0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=datetime(2026, 1, 1, tzinfo=UTC))
    fr = FilterResult(
        article=_article(title="x", summary="tech and noisebad together"),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.breakdown.get("penalties", 0) < 0
    assert score.explanation.matched_negative_keywords
    assert score.points >= 0
    assert score.points < 10


def test_scoring_recency_bonus_does_not_flip_strong_vs_weak() -> None:
    """Same-age articles: strong content scores above include-only; recency equal."""
    ref = datetime(2026, 6, 1, tzinfo=UTC)
    settings = Settings(
        include_keywords="onlyinc",
        score_strong_keywords="onlystrong",
        score_technical_keywords="",
        score_negative_keywords="",
        score_weight_include_keyword=5,
        score_weight_strong_keyword=12,
        score_weight_title_match_bonus=0,
        score_weight_recency_max=4,
        score_recency_window_days=14.0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=ref)
    inc = FilterResult(
        article=_article(title="t", summary="onlyinc", published_at=ref - timedelta(days=1)),
        passed=True,
    )
    st = FilterResult(
        article=_article(title="t", summary="onlystrong", published_at=ref - timedelta(days=1)),
        passed=True,
    )
    p_inc = scorer.score([inc])[0].points
    p_st = scorer.score([st])[0].points
    assert p_st > p_inc


def test_scoring_effective_recency_override() -> None:
    ref = datetime(2026, 1, 1, tzinfo=UTC)
    settings = Settings(
        score_weight_recency_max=10,
        score_recency_max_points=2,
        score_recency_window_days=10.0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=ref)
    fr = FilterResult(
        article=_article(title="t", published_at=ref),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.breakdown.get("recency", 0) <= 2


def test_scoring_selection_summary_lists_signals() -> None:
    settings = Settings(
        include_keywords="alpha",
        score_strong_keywords="beta",
        score_technical_keywords="gamma",
        score_negative_keywords="",
        score_weight_recency_max=0,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=datetime(2026, 1, 1, tzinfo=UTC))
    fr = FilterResult(
        article=_article(title="x", summary="alpha beta gamma"),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.selection_summary
    assert "beta" in score.explanation.selection_summary
