from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from habr_tech_radar.delivery.html_message import (
    TELEGRAM_MAX_MESSAGE_LENGTH,
    format_radar_item_html,
    truncate_for_telegram,
)
from habr_tech_radar.models.article import RadarItem
from habr_tech_radar.settings import Settings

logger = logging.getLogger(__name__)

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
DEFAULT_HTTP_TIMEOUT_SECONDS = 60.0


class TelegramConfigurationError(ValueError):
    """Settings are invalid for live Telegram delivery (missing token or chat id)."""


def telegram_credentials_ok(settings: Settings) -> bool:
    """True when both bot token and chat id are non-empty after strip."""
    token = (settings.telegram_bot_token or "").strip()
    chat = (settings.telegram_chat_id or "").strip()
    return bool(token and chat)


def _parse_telegram_response(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Telegram API returned non-JSON body: {e!s}") from e
    if not isinstance(data, dict):
        raise RuntimeError("Telegram API JSON root must be an object")
    return data


def _send_message_payload(*, chat_id: str, text: str) -> dict[str, Any]:
    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


class HttpTelegramDelivery:
    """Send RadarItem messages via Telegram Bot API (sendMessage), or log in dry_run."""

    def __init__(
        self,
        settings: Settings,
        *,
        urlopen_impl: Callable[..., Any] | None = None,
        http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._urlopen_impl = urlopen_impl if urlopen_impl is not None else urlopen
        self._http_timeout_seconds = http_timeout_seconds

    def send(self, items: list[RadarItem]) -> None:
        if not items:
            logger.info(
                "delivery: telegram: 0 item(s) selected; nothing to send (no Telegram calls)"
            )
            return

        if self._settings.dry_run:
            self._send_dry_run(items)
            return

        token = (self._settings.telegram_bot_token or "").strip()
        chat_id = (self._settings.telegram_chat_id or "").strip()
        if not token or not chat_id:
            raise TelegramConfigurationError(
                "Live Telegram delivery requires HTR_TELEGRAM_BOT_TOKEN and "
                "HTR_TELEGRAM_CHAT_ID (non-empty). Set HTR_DRY_RUN=true to preview only."
            )

        for item in items:
            text, truncated = self._format_and_truncate(item)
            if truncated:
                logger.warning(
                    "delivery: telegram: message truncated to %d chars (Telegram limit)",
                    TELEGRAM_MAX_MESSAGE_LENGTH,
                )
            self._post_send_message(token, chat_id, text)

    def _format_and_truncate(self, item: RadarItem) -> tuple[str, bool]:
        raw = format_radar_item_html(item)
        return truncate_for_telegram(raw)

    def _send_dry_run(self, items: list[RadarItem]) -> None:
        for item in items:
            text, truncated = self._format_and_truncate(item)
            if truncated:
                logger.warning(
                    "delivery: telegram dry_run: message truncated to %d chars",
                    TELEGRAM_MAX_MESSAGE_LENGTH,
                )
            logger.info("delivery: telegram dry_run would send:\n%s", text)

    def _post_send_message(self, token: str, chat_id: str, text: str) -> None:
        url = TELEGRAM_SEND_MESSAGE_URL.format(token=token)
        payload = _send_message_payload(chat_id=chat_id, text=text)
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with self._urlopen_impl(request, timeout=self._http_timeout_seconds) as resp:
                raw = resp.read()
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Telegram HTTP {e.code} for sendMessage: {err_body}") from e
        except URLError as e:
            raise RuntimeError(f"Telegram network error: {e!s}") from e

        parsed = _parse_telegram_response(raw)
        if not parsed.get("ok"):
            desc = parsed.get("description", raw[:500])
            raise RuntimeError(f"Telegram API error: {desc!r}")
