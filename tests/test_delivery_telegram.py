from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from habr_tech_radar.delivery import http_telegram as http_telegram_mod
from habr_tech_radar.delivery.html_message import (
    TELEGRAM_MAX_MESSAGE_LENGTH,
    format_radar_item_html,
    truncate_for_telegram,
)
from habr_tech_radar.delivery.http_telegram import (
    HttpTelegramDelivery,
    TelegramConfigurationError,
    TelegramDeliveryError,
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


def _http_error(
    code: int,
    body: bytes = b"{}",
    headers: dict[str, str] | None = None,
) -> HTTPError:
    from email.message import Message

    m = Message()
    if headers:
        for k, v in headers.items():
            m[k] = v
    return HTTPError(
        "https://api.telegram.org/botT/sendMessage",
        code,
        "err",
        m,
        BytesIO(body),
    )


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


def test_retry_delay_exponential_respects_cap() -> None:
    assert http_telegram_mod._retry_delay_exponential(0, 1.0) == 1.0
    assert (
        http_telegram_mod._retry_delay_exponential(10, 1.0)
        == http_telegram_mod._RETRY_DELAY_CAP_SECONDS
    )


def test_live_retry_on_503_then_success() -> None:
    calls: list[int] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(503, b'{"ok":false}')
        return _FakeHttpResponse(b'{"ok":true,"result":{"message_id":1}}')

    delivery = HttpTelegramDelivery(
        Settings(
            dry_run=False,
            telegram_bot_token="T",
            telegram_chat_id="1",
            telegram_send_max_attempts=4,
            telegram_retry_base_seconds=1.0,
        ),
        urlopen_impl=fake_urlopen,
        sleep_fn=lambda _x: None,
    )
    delivery.send([_radar_with()])
    assert len(calls) == 2


def test_live_no_retry_on_http_401() -> None:
    calls: list[int] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(1)
        raise _http_error(401, b'{"ok":false,"description":"Unauthorized"}')

    delivery = HttpTelegramDelivery(
        Settings(
            dry_run=False,
            telegram_bot_token="T",
            telegram_chat_id="1",
            telegram_send_max_attempts=4,
        ),
        urlopen_impl=fake_urlopen,
        sleep_fn=lambda _x: None,
    )
    with pytest.raises(TelegramDeliveryError):
        delivery.send([_radar_with()])
    assert len(calls) == 1


def test_live_http_429_uses_retry_after_header() -> None:
    calls: list[int] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(429, b"{}", headers={"Retry-After": "1"})
        return _FakeHttpResponse(b'{"ok":true}')

    sleeps: list[float] = []

    def track_sleep(s: float) -> None:
        sleeps.append(s)

    delivery = HttpTelegramDelivery(
        Settings(dry_run=False, telegram_bot_token="T", telegram_chat_id="1"),
        urlopen_impl=fake_urlopen,
        sleep_fn=track_sleep,
    )
    delivery.send([_radar_with()])
    assert len(calls) == 2
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(1.0)


def test_live_ok_false_unauthorized_no_retry() -> None:
    calls: list[int] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(1)
        return _FakeHttpResponse(b'{"ok":false,"error_code":401,"description":"Unauthorized"}')

    delivery = HttpTelegramDelivery(
        Settings(dry_run=False, telegram_bot_token="T", telegram_chat_id="1"),
        urlopen_impl=fake_urlopen,
        sleep_fn=lambda _x: None,
    )
    with pytest.raises(TelegramDeliveryError):
        delivery.send([_radar_with()])
    assert len(calls) == 1


def test_live_ok_false_flood_retries_then_success() -> None:
    n = [0]

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        n[0] += 1
        if n[0] == 1:
            return _FakeHttpResponse(
                b'{"ok":false,"error_code":429,"parameters":{"retry_after":1}}'
            )
        return _FakeHttpResponse(b'{"ok":true}')

    delivery = HttpTelegramDelivery(
        Settings(dry_run=False, telegram_bot_token="T", telegram_chat_id="1"),
        urlopen_impl=fake_urlopen,
        sleep_fn=lambda _x: None,
    )
    delivery.send([_radar_with()])
    assert n[0] == 2


def test_retry_logged_with_article_id(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[int] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(503)
        return _FakeHttpResponse(b'{"ok":true}')

    caplog.set_level("WARNING")
    delivery = HttpTelegramDelivery(
        Settings(
            dry_run=False,
            telegram_bot_token="T",
            telegram_chat_id="1",
            telegram_send_max_attempts=4,
        ),
        urlopen_impl=fake_urlopen,
        sleep_fn=lambda _x: None,
    )
    delivery.send([_radar_with()])
    joined = " ".join(rec.message for rec in caplog.records)
    assert "retry" in joined
    assert "article_id=x1" in joined


def test_global_delivery_budget_skips_remaining_articles() -> None:
    """After first send, monotonic clock jumps past deadline — no further HTTP or retries."""
    clock = [0.0]

    def mono() -> float:
        return clock[0]

    calls: list[int] = []

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        calls.append(1)
        clock[0] = 10.0
        return _FakeHttpResponse(b'{"ok":true,"result":{"message_id":1}}')

    item2 = RadarItem(
        score=ArticleScore(
            article=Article.model_validate(
                {
                    "id": "x2",
                    "title": "Second",
                    "url": "https://habr.com/ru/post/2/",
                    "published_at": datetime(2026, 1, 15, 12, 30, tzinfo=UTC),
                }
            ),
            points=1,
            explanation=ScoreExplanation(),
            reasons=[],
        )
    )
    item1 = _radar_with()

    delivery = HttpTelegramDelivery(
        Settings(
            dry_run=False,
            telegram_bot_token="T",
            telegram_chat_id="1",
            telegram_max_delivery_seconds=1.0,
            telegram_send_max_attempts=10,
        ),
        urlopen_impl=fake_urlopen,
        sleep_fn=lambda _x: None,
        monotonic_fn=mono,
    )
    with pytest.raises(TelegramDeliveryError) as excinfo:
        delivery.send([item1, item2])
    stats = excinfo.value.stats
    assert stats is not None
    assert stats.sent == 1
    assert stats.skipped_due_budget == 1
    assert len(calls) == 1


def test_dry_run_logs_start_and_summary(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")

    def fake_urlopen(req: Request, timeout: float = 0) -> Any:
        raise AssertionError("no HTTP in dry_run")

    delivery = HttpTelegramDelivery(Settings(dry_run=True), urlopen_impl=fake_urlopen)
    delivery.send([_radar_with()])
    joined = " ".join(rec.message for rec in caplog.records)
    assert "delivery: telegram: start mode=dry_run selected=1" in joined
    assert "delivery: telegram: summary mode=dry_run selected=1 sent=1 failed=0" in joined
