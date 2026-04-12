from __future__ import annotations

import contextlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any, Literal
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
_RETRY_DELAY_CAP_SECONDS = 30.0

_SendAttemptOutcome = Literal["ok"] | tuple[Literal["retry", "permanent"], str, float | None]


class _ItemSendFailed(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TelegramConfigurationError(ValueError):
    """Settings are invalid for live Telegram delivery (missing token or chat id)."""


class TelegramDeliveryError(RuntimeError):
    """One or more messages could not be delivered after retries (live mode)."""


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


def _retry_delay_exponential(attempt_zero_index: int, base_seconds: float) -> float:
    delay = base_seconds * float(2**attempt_zero_index)
    return float(min(_RETRY_DELAY_CAP_SECONDS, delay))


def _retry_after_from_json_body(body: bytes) -> float | None:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    params = data.get("parameters")
    if isinstance(params, dict):
        ra = params.get("retry_after")
        if isinstance(ra, (int, float)):
            return float(ra)
    return None


def _parse_retry_after_header(value: str | None) -> float | None:
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _telegram_ok_false_is_permanent(parsed: dict[str, Any]) -> bool:
    """True when ok:false should not be retried (misconfiguration / bad request)."""
    code = parsed.get("error_code")
    desc = str(parsed.get("description", "")).lower()
    if code in (400, 401, 403, 404):
        return True
    return bool(
        "unauthorized" in desc
        or "not found" in desc
        or "bad request" in desc
        or "chat not found" in desc
        or "bot was blocked" in desc
    )


def _telegram_ok_false_should_retry(parsed: dict[str, Any]) -> tuple[bool, float | None]:
    """Whether to retry on HTTP 200 with ok:false; optional sleep from API."""
    code = parsed.get("error_code")
    params = parsed.get("parameters")
    sleep_hint: float | None = None
    if isinstance(params, dict):
        ra = params.get("retry_after")
        if isinstance(ra, (int, float)):
            sleep_hint = float(ra)
    if code == 429:
        return True, sleep_hint
    if sleep_hint is not None and sleep_hint > 0:
        return True, sleep_hint
    desc = str(parsed.get("description", "")).lower()
    if "too many requests" in desc or "retry after" in desc or "flood" in desc:
        return True, sleep_hint
    return False, None


class HttpTelegramDelivery:
    """Send RadarItem messages via Telegram Bot API (sendMessage), or log in dry_run."""

    def __init__(
        self,
        settings: Settings,
        *,
        urlopen_impl: Callable[..., Any] | None = None,
        http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings
        self._urlopen_impl = urlopen_impl if urlopen_impl is not None else urlopen
        self._http_timeout_seconds = http_timeout_seconds
        self._sleep_fn = sleep_fn if sleep_fn is not None else time.sleep

    def send(self, items: list[RadarItem]) -> None:
        if not items:
            logger.info(
                "delivery: telegram: 0 item(s) selected; nothing to send (no Telegram calls)"
            )
            return

        mode = "dry_run" if self._settings.dry_run else "live"
        n = len(items)
        logger.info("delivery: telegram: start mode=%s selected=%d", mode, n)

        if self._settings.dry_run:
            self._send_dry_run(items)
            logger.info(
                "delivery: telegram: summary mode=dry_run selected=%d sent=%d failed=0",
                n,
                n,
            )
            return

        token = (self._settings.telegram_bot_token or "").strip()
        chat_id = (self._settings.telegram_chat_id or "").strip()
        if not token or not chat_id:
            raise TelegramConfigurationError(
                "Live Telegram delivery requires HTR_TELEGRAM_BOT_TOKEN and "
                "HTR_TELEGRAM_CHAT_ID (non-empty). Set HTR_DRY_RUN=true to preview only."
            )

        max_attempts = self._settings.telegram_send_max_attempts
        base = self._settings.telegram_retry_base_seconds
        sent = 0
        failed = 0

        for item in items:
            article_id = item.score.article.id
            text, truncated = self._format_and_truncate(item)
            if truncated:
                logger.warning(
                    "delivery: telegram: message truncated to %d chars (Telegram limit)",
                    TELEGRAM_MAX_MESSAGE_LENGTH,
                )
            try:
                self._post_send_message_with_retries(
                    token, chat_id, text, article_id, max_attempts=max_attempts, base_seconds=base
                )
                sent += 1
            except _ItemSendFailed as e:
                failed += 1
                logger.warning(
                    "delivery: telegram: failed article_id=%s reason=%s",
                    article_id,
                    e.reason,
                )

        logger.info(
            "delivery: telegram: summary mode=live selected=%d sent=%d failed=%d",
            n,
            sent,
            failed,
        )
        if failed:
            raise TelegramDeliveryError(
                f"Telegram delivery incomplete: failed={failed} sent={sent} selected={n}"
            )

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

    def _post_send_message_with_retries(
        self,
        token: str,
        chat_id: str,
        text: str,
        article_id: str,
        *,
        max_attempts: int,
        base_seconds: float,
    ) -> None:
        last_reason = "unknown"
        for attempt in range(1, max_attempts + 1):
            outcome = self._send_message_single_attempt(token, chat_id, text)
            if outcome == "ok":
                return
            kind, reason, sleep_hint = outcome
            last_reason = reason
            if kind == "permanent":
                raise _ItemSendFailed(reason) from None
            if attempt >= max_attempts:
                break
            if sleep_hint is not None and sleep_hint > 0:
                delay = min(_RETRY_DELAY_CAP_SECONDS, sleep_hint)
            else:
                delay = _retry_delay_exponential(attempt - 1, base_seconds)
            logger.warning(
                "delivery: telegram: retry article_id=%s attempt=%d/%d reason=%s sleep_s=%.1f",
                article_id,
                attempt,
                max_attempts,
                reason,
                delay,
            )
            self._sleep_fn(delay)

        raise _ItemSendFailed(last_reason)

    def _send_message_single_attempt(
        self, token: str, chat_id: str, text: str
    ) -> _SendAttemptOutcome:
        """Return 'ok' or ('retry'|'permanent', reason, sleep_hint)."""
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
            return self._classify_http_error(e)
        except (URLError, OSError) as e:
            return ("retry", f"network:{type(e).__name__}", None)

        try:
            parsed = _parse_telegram_response(raw)
        except RuntimeError as e:
            return ("retry", f"parse:{e}", None)

        if parsed.get("ok"):
            return "ok"

        if _telegram_ok_false_is_permanent(parsed):
            desc = parsed.get("description", "")
            return ("permanent", f"api_ok_false:{desc!s}"[:200], None)

        should_retry, sleep_hint = _telegram_ok_false_should_retry(parsed)
        if should_retry:
            return ("retry", "api_flood_or_rate", sleep_hint)

        desc = parsed.get("description", "")
        return ("permanent", f"api_ok_false:{desc!s}"[:200], None)

    def _classify_http_error(self, e: HTTPError) -> _SendAttemptOutcome:
        code = e.code
        body = b""
        with contextlib.suppress(OSError):
            body = e.read()
        err_snip = body.decode("utf-8", errors="replace")[:500]

        if code == 429:
            hdrs = getattr(e, "headers", None)
            ra_raw = hdrs.get("Retry-After") if hdrs is not None else None
            ra_hdr = _parse_retry_after_header(str(ra_raw) if ra_raw is not None else None)
            ra_body = _retry_after_from_json_body(body)
            sleep_hint = ra_hdr or ra_body
            return ("retry", "http_429", sleep_hint)

        if code in (500, 502, 503, 504):
            return ("retry", f"http_{code}", None)

        if code in (400, 401, 403, 404):
            return ("permanent", f"http_{code}:{err_snip}", None)

        if 400 <= code < 500:
            return ("permanent", f"http_{code}:{err_snip}", None)

        return ("retry", f"http_{code}:{err_snip}", None)
