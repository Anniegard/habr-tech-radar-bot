from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from habr_tech_radar.models.article import Article, FilterResult

logger = logging.getLogger(__name__)


@runtime_checkable
class ArticleFilter(Protocol):
    """Filters articles by keywords, hubs, blocklists, etc. TODO: real rules."""

    def filter(self, articles: list[Article]) -> list[FilterResult]: ...


class StubArticleFilter:
    """Pass-through: marks all articles as passed."""

    def filter(self, articles: list[Article]) -> list[FilterResult]:
        out = [FilterResult(article=a, passed=True, reason="stub pass-through") for a in articles]
        logger.info("filtering: stub evaluated %d article(s)", len(out))
        return out
