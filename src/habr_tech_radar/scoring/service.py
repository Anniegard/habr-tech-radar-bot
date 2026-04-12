from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from habr_tech_radar.models.article import ArticleScore, FilterResult

logger = logging.getLogger(__name__)


@runtime_checkable
class ArticleScoring(Protocol):
    """Assigns relevance scores. TODO: heuristics + optional LLM signals."""

    def score(self, filtered: list[FilterResult]) -> list[ArticleScore]: ...


class StubArticleScoring:
    """Assigns a fixed mid-range score to passed articles."""

    def score(self, filtered: list[FilterResult]) -> list[ArticleScore]:
        scores: list[ArticleScore] = []
        for fr in filtered:
            if not fr.passed:
                continue
            scores.append(
                ArticleScore(
                    article=fr.article,
                    value=0.5,
                    reasons=["stub default score"],
                )
            )
        logger.info("scoring: stub scored %d article(s)", len(scores))
        return scores
