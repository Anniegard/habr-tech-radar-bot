from __future__ import annotations

import logging
from dataclasses import dataclass

from habr_tech_radar.delivery.http_telegram import (
    HttpTelegramDelivery,
    TelegramConfigurationError,
    TelegramDeliveryError,
    telegram_credentials_ok,
)
from habr_tech_radar.delivery.service import TelegramDelivery
from habr_tech_radar.delivery.stats import DeliveryStats
from habr_tech_radar.filtering.heuristic import HeuristicArticleFilter
from habr_tech_radar.filtering.service import ArticleFilter
from habr_tech_radar.ingestion.rss import RssHabrIngestion
from habr_tech_radar.ingestion.service import HabrIngestion, StubHabrIngestion
from habr_tech_radar.llm.service import LLMEnrichment, NoOpLLMEnrichment
from habr_tech_radar.models.article import RadarItem
from habr_tech_radar.scoring.heuristic import HeuristicArticleScoring
from habr_tech_radar.scoring.service import ArticleScoring
from habr_tech_radar.selection import select_top_scored
from habr_tech_radar.settings import Settings, effective_state_file
from habr_tech_radar.state.seen_store import SeenArticleStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    items: list[RadarItem]
    fetched_count: int
    selected_count: int
    delivery_stats: DeliveryStats


@dataclass(frozen=True)
class PipelineComponents:
    ingestion: HabrIngestion
    article_filter: ArticleFilter
    scoring: ArticleScoring
    llm: LLMEnrichment
    delivery: TelegramDelivery
    max_selected_articles: int


def run_pipeline(components: PipelineComponents) -> PipelineResult:
    """Execute ingest → filter → score → enrich → deliver."""
    articles = components.ingestion.fetch_new()
    fetched_count = len(articles)
    filtered = components.article_filter.filter(articles)
    scores = components.scoring.score(filtered)
    top = select_top_scored(scores, components.max_selected_articles)
    logger.info("selection: top %d article(s) after ranking", len(top))
    items = components.llm.enrich(top)
    selected_count = len(items)
    try:
        delivery_stats = components.delivery.send(items)
    except TelegramDeliveryError as e:
        raise TelegramDeliveryError(
            str(e),
            stats=e.stats,
            fetched_count=fetched_count,
            selected_count=selected_count,
        ) from e
    logger.info("pipeline: completed with %d radar item(s)", len(items))
    return PipelineResult(
        items=items,
        fetched_count=fetched_count,
        selected_count=selected_count,
        delivery_stats=delivery_stats,
    )


def _resolve_telegram_delivery(settings: Settings) -> TelegramDelivery:
    """HTTP Telegram when dry_run or creds OK; live mode without creds fails fast."""
    if settings.dry_run:
        return HttpTelegramDelivery(settings)
    if telegram_credentials_ok(settings):
        return HttpTelegramDelivery(settings)
    raise TelegramConfigurationError(
        "HTR_DRY_RUN=false requires both HTR_TELEGRAM_BOT_TOKEN and HTR_TELEGRAM_CHAT_ID "
        "(non-empty). Set HTR_DRY_RUN=true to run without sending to Telegram, or add credentials."
    )


def default_components(settings: Settings) -> PipelineComponents:
    """Wire default implementations: demo uses stub ingestion; otherwise RSS + seen IDs."""
    if settings.demo_mode:
        ingestion: HabrIngestion = StubHabrIngestion(demo_mode=True)
    else:
        store = SeenArticleStore(effective_state_file(settings))
        ingestion = RssHabrIngestion(settings=settings, store=store)
    return PipelineComponents(
        ingestion=ingestion,
        article_filter=HeuristicArticleFilter(settings),
        scoring=HeuristicArticleScoring(settings),
        llm=NoOpLLMEnrichment(),
        delivery=_resolve_telegram_delivery(settings),
        max_selected_articles=settings.max_selected_articles,
    )
