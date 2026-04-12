from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from habr_tech_radar.models.article import ArticleScore, RadarItem

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMEnrichment(Protocol):
    """Optional enrichment (summary, tags). TODO: OpenAI or other provider."""

    def enrich(self, scores: list[ArticleScore]) -> list[RadarItem]: ...


class NoOpLLMEnrichment:
    """Does not call external APIs; wraps scores as RadarItem."""

    def enrich(self, scores: list[ArticleScore]) -> list[RadarItem]:
        items = [RadarItem(score=s, enriched_summary=None) for s in scores]
        logger.info("llm: no-op enrichment for %d item(s)", len(items))
        return items
