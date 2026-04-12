from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from habr_tech_radar.delivery.stats import DeliveryStats
from habr_tech_radar.models.article import RadarItem

logger = logging.getLogger(__name__)


@runtime_checkable
class TelegramDelivery(Protocol):
    """Sends radar items to Telegram (e.g. HttpTelegramDelivery or LogOnlyTelegramDelivery)."""

    def send(self, items: list[RadarItem]) -> DeliveryStats: ...


class LogOnlyTelegramDelivery:
    """Logs items at INFO; does not require tokens or network."""

    def send(self, items: list[RadarItem]) -> DeliveryStats:
        for item in items:
            a = item.score.article
            logger.info(
                "delivery: would send - points=%d title=%r url=%s",
                item.score.points,
                a.title,
                str(a.url),
            )
        if not items:
            logger.info("delivery: nothing to send")
        return DeliveryStats(sent=len(items), failed=0, skipped_due_budget=0)
