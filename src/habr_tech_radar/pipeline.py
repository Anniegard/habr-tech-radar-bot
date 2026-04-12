from __future__ import annotations

import logging
from dataclasses import dataclass

from habr_tech_radar.delivery.service import LogOnlyTelegramDelivery, TelegramDelivery
from habr_tech_radar.filtering.service import ArticleFilter, StubArticleFilter
from habr_tech_radar.ingestion.service import HabrIngestion, StubHabrIngestion
from habr_tech_radar.llm.service import LLMEnrichment, NoOpLLMEnrichment
from habr_tech_radar.models.article import RadarItem
from habr_tech_radar.scoring.service import ArticleScoring, StubArticleScoring

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineComponents:
    ingestion: HabrIngestion
    article_filter: ArticleFilter
    scoring: ArticleScoring
    llm: LLMEnrichment
    delivery: TelegramDelivery


def run_pipeline(components: PipelineComponents) -> list[RadarItem]:
    """Execute ingest → filter → score → enrich → deliver."""
    articles = components.ingestion.fetch_new()
    filtered = components.article_filter.filter(articles)
    scores = components.scoring.score(filtered)
    items = components.llm.enrich(scores)
    components.delivery.send(items)
    logger.info("pipeline: completed with %d radar item(s)", len(items))
    return items


def default_components(*, demo_mode: bool) -> PipelineComponents:
    """Wire stub implementations for local development."""
    return PipelineComponents(
        ingestion=StubHabrIngestion(demo_mode=demo_mode),
        article_filter=StubArticleFilter(),
        scoring=StubArticleScoring(),
        llm=NoOpLLMEnrichment(),
        delivery=LogOnlyTelegramDelivery(),
    )
