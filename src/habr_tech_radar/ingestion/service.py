from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from habr_tech_radar.models.article import Article

logger = logging.getLogger(__name__)


@runtime_checkable
class HabrIngestion(Protocol):
    """Fetches or parses new articles from Habr. Real implementation: RSS/API. TODO."""

    def fetch_new(self) -> list[Article]:
        """Return newly seen articles since last run (implementation-defined)."""
        ...


class StubHabrIngestion:
    """Safe default: no network. Returns nothing unless demo_mode is enabled."""

    def __init__(self, *, demo_mode: bool = False) -> None:
        self._demo_mode = demo_mode

    def fetch_new(self) -> list[Article]:
        if not self._demo_mode:
            logger.info("ingestion: stub returned no articles (set HTR_DEMO_MODE=1 for demo)")
            return []
        # TODO: replace with RSS/API ingestion; demo data only for local pipeline smoke tests
        demo = Article.model_validate(
            {
                "id": "demo-1",
                "title": "Demo: Habr Tech Radar",
                "url": "https://habr.com/ru/articles/000000/",
                "summary": "Synthetic article for local testing.",
                "metadata": {"source": "stub"},
            }
        )
        logger.info("ingestion: demo mode - returning one synthetic article")
        return [demo]
