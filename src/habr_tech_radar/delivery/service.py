from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from habr_tech_radar.models.article import RadarItem

logger = logging.getLogger(__name__)


@runtime_checkable
class TelegramDelivery(Protocol):
    """Sends radar items to Telegram. TODO: python-telegram-bot or HTTP API."""

    def send(self, items: list[RadarItem]) -> None: ...


class LogOnlyTelegramDelivery:
    """Logs items at INFO; does not require tokens or network."""

    def send(self, items: list[RadarItem]) -> None:
        for item in items:
            a = item.score.article
            logger.info(
                "delivery: would send - score=%.2f title=%r url=%s",
                item.score.value,
                a.title,
                str(a.url),
            )
        if not items:
            logger.info("delivery: nothing to send")
