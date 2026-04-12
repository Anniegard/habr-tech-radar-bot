from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from urllib.request import Request

import pytest

from habr_tech_radar.delivery.html_message import (
    TELEGRAM_MAX_MESSAGE_LENGTH,
    format_radar_item_html,
    truncate_for_telegram,
)
from habr_tech_radar.delivery.http_telegram import (
    HttpTelegramDelivery,
    TelegramConfigurationError,
    telegram_credentials_ok,
)
from habr_tech_radar.models.article import Article, ArticleScore, RadarItem, ScoreExplanation
from habr_tech_radar.pipeline import default_components
from habr_tech_radar.settings import Settings


def _radar_with(
    *,
    title: str = "Hello",
    summary: str | None = None,
    reasons: list[str] | None = None,
    expl: ScoreExplanation | None = None,
) -> RadarItem:
    article = Article.model_validate(
        {
            "id": "x1",
            "title": title,
            "url": "https://habr.com/ru/post/1/",
            "published_at": datetime(2026, 1, 15, 12, 30, tzinfo=UTC),
            "summary": summary,
        }
    )
    score = ArticleScore(
        article=article,
        points=42,
        explanation=expl or ScoreExplanation(),
        reasons=reasons or [],
    )
    return RadarItem(score=score)


def test_format_radar_item_html_escapes_user_content() -> None:
    item = _radar_with(
        title='Evil <b>bold</b> & "quotes"',
        summary="<script>x</script>",
        reasons=["line with <tag> & ampersand"],
        expl=ScoreExplanation(
            matched_include_keywords=["<kw>", "python"],
            matched_include_hubs=["&hub;"],
            breakdown={"include_keywords": 10},
        ),
    )
    html = format_radar_item_html(item)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert "&amp;" in html
    assert "python" in html


def test_truncate_for_telegram_adds_suffix() -> None:
    long = "a" * (TELEGRAM_MAX_MESSAGE_LENGTH + 100)
    out, truncated = truncate_for_telegram(long)
    assert truncated
    assert len(out) <= TELEGRAM_MAX_MESSAGE_LENGTH
    assert "truncated" in out


def test_telegram_credentials_ok() -> None:
    assert telegram_credentials_ok(Settings(telegram_bot_token="t", telegram_chat_id="1"))
    assert not telegram_credentials_ok(Settings(telegram_bot_token=None, telegram_chat_id="1"))
    assert not telegram_credentials_ok(Settings(telegram_bot_token="  ", telegram_chat_id="1"))


class _FakeHttpResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_dry_run_does_not_invoke_http() -> None:
    calls: list[Request] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(req)
        return _FakeHttpResponse(b'{"ok":true}')

    delivery = HttpTelegramDelivery(
        Settings(dry_run=True),
        urlopen_impl=fake_urlopen,
    )
    delivery.send([_radar_with()])
    assert calls == []


def test_live_send_posts_expected_json() -> None:
    calls: list[Request] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(req)
        return _FakeHttpResponse(b'{"ok":true,"result":{"message_id":1}}')

    delivery = HttpTelegramDelivery(
        Settings(
            dry_run=False,
            telegram_bot_token="TEST_TOKEN",
            telegram_chat_id="999",
        ),
        urlopen_impl=fake_urlopen,
    )
    delivery.send([_radar_with(title="Hi")])

    assert len(calls) == 1
    req = calls[0]
    assert "/botTEST_TOKEN/sendMessage" in req.full_url
    raw_data = req.data
    assert isinstance(raw_data, (bytes, bytearray))
    body = json.loads(bytes(raw_data).decode("utf-8"))
    assert body["chat_id"] == "999"
    assert body["parse_mode"] == "HTML"
    assert body["disable_web_page_preview"] is True
    assert "<b>Hi</b>" in body["text"]


def test_live_send_without_credentials_raises() -> None:
    delivery = HttpTelegramDelivery(
        Settings(dry_run=False, telegram_bot_token=None, telegram_chat_id=None),
    )
    with pytest.raises(TelegramConfigurationError):
        delivery.send([_radar_with()])


def test_empty_items_no_http_call() -> None:
    mock_open = MagicMock()
    delivery = HttpTelegramDelivery(
        Settings(dry_run=False, telegram_bot_token="t", telegram_chat_id="c"),
        urlopen_impl=mock_open,
    )
    delivery.send([])
    mock_open.assert_not_called()


@pytest.mark.parametrize(
    ("dry_run", "token", "chat", "expect_type", "expect_error"),
    [
        (True, None, None, HttpTelegramDelivery, None),
        (True, "tok", "1", HttpTelegramDelivery, None),
        (False, "tok", "1", HttpTelegramDelivery, None),
        (False, None, "1", None, TelegramConfigurationError),
        (False, "tok", None, None, TelegramConfigurationError),
        (False, "", "", None, TelegramConfigurationError),
    ],
)
def test_default_components_telegram_wiring(
    dry_run: bool,
    token: str | None,
    chat: str | None,
    expect_type: type | None,
    expect_error: type[Exception] | None,
) -> None:
    s = Settings(
        demo_mode=True,
        dry_run=dry_run,
        telegram_bot_token=token,
        telegram_chat_id=chat,
    )
    if expect_error is not None:
        with pytest.raises(expect_error):
            default_components(s)
        return
    assert expect_type is not None
    c = default_components(s)
    assert isinstance(c.delivery, expect_type)
    assert not type(c.delivery).__name__.startswith("LogOnly")
