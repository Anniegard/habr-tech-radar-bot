from __future__ import annotations

from datetime import UTC, datetime

import pytest

from habr_tech_radar.models.article import Article, ArticleScore, ScoreExplanation
from habr_tech_radar.selection import select_top_scored


def _mk_score(
    article_id: str,
    points: int,
    published_at: datetime,
) -> ArticleScore:
    return ArticleScore(
        article=Article.model_validate(
            {
                "id": article_id,
                "title": "t",
                "url": "https://habr.com/ru/post/1/",
                "published_at": published_at,
            }
        ),
        points=points,
        explanation=ScoreExplanation(),
    )


def test_select_top_n_limits_count() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    scores = [
        _mk_score("low", 1, base),
        _mk_score("mid", 5, base),
        _mk_score("high", 10, base),
    ]
    top = select_top_scored(scores, 2)
    assert len(top) == 2
    assert [s.points for s in top] == [10, 5]


def test_tie_break_newer_publish_first() -> None:
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 2, 1, tzinfo=UTC)
    scores = [
        _mk_score("a", 5, older),
        _mk_score("b", 5, newer),
    ]
    top = select_top_scored(scores, 2)
    assert top[0].article.id == "b"


def test_tie_break_same_points_and_time_uses_id() -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    scores = [
        _mk_score("z", 3, t),
        _mk_score("m", 3, t),
        _mk_score("a", 3, t),
    ]
    top = select_top_scored(scores, 3)
    assert [s.article.id for s in top] == ["a", "m", "z"]


def test_select_top_invalid_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        select_top_scored([], 0)
