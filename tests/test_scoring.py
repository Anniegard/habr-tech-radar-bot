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


def test_keyword_score_is_capped_to_50() -> None:
    settings = Settings(
        include_keywords="k1,k2,k3,k4,k5,k6,k7,k8,k9,k10",
        score_strong_keywords="s1,s2,s3,s4,s5,s6,s7,s8,s9,s10",
        score_technical_keywords="t1,t2,t3,t4,t5,t6,t7,t8,t9,t10",
        score_negative_keywords="",
        score_weight_include_keyword=5,
        score_weight_strong_keyword=12,
        score_weight_technical_signal=10,
        score_weight_include_hub=8,
        score_weight_title_match_bonus=3,
        score_weight_recency_max=10,
        keyword_score_max=50,
        llm_scoring_enabled=False,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=datetime(2026, 4, 1, tzinfo=UTC))
    fr = FilterResult(
        article=_article(
            title=" ".join(["k1", "s1", "t1"]),
            summary=" ".join(
                [
                    "k1",
                    "k2",
                    "k3",
                    "k4",
                    "k5",
                    "k6",
                    "k7",
                    "k8",
                    "k9",
                    "k10",
                    "s1",
                    "s2",
                    "s3",
                    "s4",
                    "s5",
                    "s6",
                    "s7",
                    "s8",
                    "s9",
                    "s10",
                    "t1",
                    "t2",
                    "t3",
                    "t4",
                    "t5",
                    "t6",
                    "t7",
                    "t8",
                    "t9",
                    "t10",
                ]
            ),
            categories=["Python", "Backend", "DevOps"],
        ),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.keyword_points == 50
    assert score.points == 50


def test_total_score_is_capped_to_100() -> None:
    class HighLLMScorer(HeuristicArticleScoring):
        def _score_llm(
            self, *, fr: FilterResult, keyword_points: int
        ) -> tuple[int, bool, str | None, bool]:
            return 50, True, None, True

    settings = Settings(
        include_keywords="alpha,beta,gamma,delta,epsilon,zeta,eta,theta",
        score_strong_keywords="strong1,strong2,strong3,strong4,strong5",
        score_technical_keywords="tech1,tech2,tech3,tech4,tech5",
        score_negative_keywords="",
        score_weight_recency_max=10,
        keyword_score_max=80,
        llm_score_max=50,
        llm_scoring_enabled=True,
        openai_api_key="x",
    )
    scorer = HighLLMScorer(settings, reference_time=datetime(2026, 4, 1, tzinfo=UTC))
    fr = FilterResult(
        article=_article(
            title="strong1 tech1 alpha",
            summary=(
                "alpha beta gamma delta epsilon zeta eta theta "
                "strong1 strong2 strong3 strong4 strong5 tech1 tech2 tech3 tech4 tech5"
            ),
        ),
        passed=True,
    )
    score = scorer.score([fr])[0]
    assert score.explanation.keyword_points > 50
    assert score.explanation.llm_points == 50
    assert score.points == 100
    assert score.explanation.total_points == 100


def test_repeated_keyword_spam_does_not_grow_unbounded() -> None:
    settings = Settings(
        include_keywords="python",
        score_strong_keywords="",
        score_technical_keywords="",
        score_negative_keywords="",
        score_weight_include_keyword=5,
        score_weight_title_match_bonus=0,
        score_weight_recency_max=0,
        keyword_score_max=50,
        llm_scoring_enabled=False,
    )
    scorer = HeuristicArticleScoring(settings, reference_time=datetime(2026, 1, 1, tzinfo=UTC))
    fr1 = FilterResult(article=_article(title="x", summary="python"), passed=True)
    fr2 = FilterResult(article=_article(title="x", summary="python " * 500), passed=True)
    s1 = scorer.score([fr1])[0].points
    s2 = scorer.score([fr2])[0].points
    assert s1 == s2


def test_llm_not_called_when_keyword_below_threshold() -> None:
    class TrackingScorer(HeuristicArticleScoring):
        def __init__(self, settings: Settings) -> None:
            super().__init__(settings, reference_time=datetime(2026, 1, 1, tzinfo=UTC))
            self.called = False

        def _score_llm(
            self, *, fr: FilterResult, keyword_points: int
        ) -> tuple[int, bool, str | None, bool]:
            self.called = True
            return super()._score_llm(fr=fr, keyword_points=keyword_points)

    scorer = TrackingScorer(
        Settings(
            include_keywords="alpha",
            score_strong_keywords="",
            score_technical_keywords="",
            score_negative_keywords="",
            score_weight_include_keyword=5,
            score_weight_title_match_bonus=0,
            score_weight_recency_max=0,
            llm_keyword_threshold=20,
            openai_api_key="x",
            llm_scoring_enabled=True,
        )
    )
    fr = FilterResult(article=_article(title="z", summary="alpha"), passed=True)
    score = scorer.score([fr])[0]
    assert scorer.called
    assert score.explanation.llm_points == 0
    assert score.explanation.llm_applied is False
    assert score.explanation.llm_fallback_reason == "keyword_threshold_not_met"


def test_llm_called_when_keyword_meets_threshold() -> None:
    class TrackingScorer(HeuristicArticleScoring):
        def __init__(self, settings: Settings) -> None:
            super().__init__(settings, reference_time=datetime(2026, 1, 1, tzinfo=UTC))
            self.called = False

        def _score_llm(
            self, *, fr: FilterResult, keyword_points: int
        ) -> tuple[int, bool, str | None, bool]:
            self.called = True
            return 7, True, None, True

    scorer = TrackingScorer(
        Settings(
            include_keywords="alpha,beta,gamma,delta",
            score_strong_keywords="",
            score_technical_keywords="",
            score_negative_keywords="",
            score_weight_include_keyword=5,
            score_weight_title_match_bonus=0,
            score_weight_recency_max=0,
            llm_keyword_threshold=20,
            llm_scoring_enabled=True,
            openai_api_key="x",
        )
    )
    fr = FilterResult(article=_article(title="z", summary="alpha beta gamma delta"), passed=True)
    score = scorer.score([fr])[0]
    assert scorer.called
    assert score.explanation.llm_applied is True
    assert score.explanation.llm_points == 7


def test_invalid_llm_json_falls_back_to_zero() -> None:
    class InvalidJsonScorer(HeuristicArticleScoring):
        def _score_llm(
            self, *, fr: FilterResult, keyword_points: int
        ) -> tuple[int, bool, str | None, bool]:
            return 0, False, "llm_request_or_parse_failed", True

    scorer = InvalidJsonScorer(
        Settings(
            include_keywords="alpha,beta,gamma,delta",
            score_strong_keywords="",
            score_technical_keywords="",
            score_negative_keywords="",
            score_weight_include_keyword=5,
            score_weight_title_match_bonus=0,
            score_weight_recency_max=0,
            llm_keyword_threshold=20,
            llm_scoring_enabled=True,
            openai_api_key="x",
        ),
        reference_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    fr = FilterResult(article=_article(title="z", summary="alpha beta gamma delta"), passed=True)
    score = scorer.score([fr])[0]
    assert score.explanation.llm_points == 0
    assert score.explanation.llm_applied is False
    assert score.explanation.llm_fallback_reason == "llm_request_or_parse_failed"


def test_article_fetch_failure_falls_back_gracefully() -> None:
    class FetchFailedScorer(HeuristicArticleScoring):
        def _score_llm(
            self, *, fr: FilterResult, keyword_points: int
        ) -> tuple[int, bool, str | None, bool]:
            return 0, False, "article_fetch_failed", False

    scorer = FetchFailedScorer(
        Settings(
            include_keywords="alpha,beta,gamma,delta",
            score_strong_keywords="",
            score_technical_keywords="",
            score_negative_keywords="",
            score_weight_include_keyword=5,
            score_weight_title_match_bonus=0,
            score_weight_recency_max=0,
            llm_keyword_threshold=20,
            llm_scoring_enabled=True,
            openai_api_key="x",
            llm_fetch_article_enabled=True,
        ),
        reference_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    fr = FilterResult(article=_article(title="z", summary="alpha beta gamma delta"), passed=True)
    score = scorer.score([fr])[0]
    assert score.explanation.llm_points == 0
    assert score.explanation.llm_applied is False
    assert score.explanation.llm_fallback_reason == "article_fetch_failed"
