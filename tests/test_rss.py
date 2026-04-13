from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from habr_tech_radar.ingestion.rss import RssHabrIngestion, parse_rss_bytes
from habr_tech_radar.settings import Settings
from habr_tech_radar.state.seen_store import SeenArticleStore

_MINIMAL_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>T</title>
<item>
  <title>Hello world</title>
  <link>https://habr.com/ru/articles/123456/</link>
  <guid isPermaLink="true">https://habr.com/ru/articles/123456/</guid>
  <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
  <description><![CDATA[<p>First <b>paragraph</b>.</p>]]></description>
  <category>Python</category>
</item>
</channel></rss>
"""


def test_parse_rss_bytes_maps_article_fields() -> None:
    articles = parse_rss_bytes(_MINIMAL_RSS, feed_url="http://example.com/feed.xml")
    assert len(articles) == 1
    a = articles[0]
    assert a.id == "habr:article:123456"
    assert a.title == "Hello world"
    assert str(a.url) == "https://habr.com/ru/articles/123456/"
    assert a.summary == "First paragraph ."
    assert a.metadata.get("feed_url") == "http://example.com/feed.xml"
    assert a.metadata.get("categories") == ["Python"]
    assert a.published_at.tzinfo == UTC
    assert a.published_at == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def test_parse_rss_bytes_skips_bad_item_keeps_good(tmp_path: Path) -> None:
    bad_and_good = b"""<?xml version="1.0"?><rss><channel>
<item><title></title><link></link></item>
<item><title>Ok</title><link>https://habr.com/ru/articles/2/</link></item>
</channel></rss>"""
    arts = parse_rss_bytes(bad_and_good, feed_url="http://x")
    assert len(arts) == 1
    assert arts[0].title == "Ok"


def test_rss_dedup_across_runs_uses_state_file(tmp_path: Path) -> None:
    state = tmp_path / "seen.json"
    settings = Settings(
        demo_mode=False,
        habr_rss_urls=["http://example.com/feed.xml"],
        state_file=state,
        rss_fetch_timeout_seconds=5.0,
    )

    def fetcher(_url: str, _timeout: float) -> bytes:
        return _MINIMAL_RSS

    first = RssHabrIngestion(
        settings=settings,
        store=SeenArticleStore(state),
        fetcher=fetcher,
    ).fetch_new()
    assert len(first) == 1

    second = RssHabrIngestion(
        settings=settings,
        store=SeenArticleStore(state),
        fetcher=fetcher,
    ).fetch_new()
    assert second == []


def test_rss_cross_feed_dedup_same_article_different_guid(tmp_path: Path) -> None:
    rss_a = b"""<?xml version="1.0"?><rss><channel>
<item>
  <title>T</title>
  <link>https://habr.com/ru/articles/777/?utm_source=a</link>
  <guid>a</guid>
</item>
</channel></rss>"""
    rss_b = b"""<?xml version="1.0"?><rss><channel>
<item>
  <title>T</title>
  <link>https://habr.com/ru/articles/777/</link>
  <guid>b-different</guid>
</item>
</channel></rss>"""
    state = tmp_path / "seen.json"
    settings = Settings(
        demo_mode=False,
        habr_rss_urls=["http://a/feed", "http://b/feed"],
        state_file=state,
    )
    feeds = iter([rss_a, rss_b])

    def fetcher(_url: str, _timeout: float) -> bytes:
        return next(feeds)

    got = RssHabrIngestion(
        settings=settings,
        store=SeenArticleStore(state),
        fetcher=fetcher,
    ).fetch_new()
    assert len(got) == 1
    assert got[0].id == "habr:article:777"


@pytest.mark.parametrize(
    ("bad_payload", "desc"),
    [
        (b"not xml", "not_xml"),
        (b'<?xml version="1.0"?><oops/>', "no_items"),
    ],
)
def test_rss_ingestion_network_failure_returns_empty(
    tmp_path: Path,
    bad_payload: bytes,
    desc: str,
) -> None:
    _ = desc
    state = tmp_path / "seen.json"
    settings = Settings(
        demo_mode=False,
        habr_rss_urls=["http://example.com/feed.xml"],
        state_file=state,
    )

    def fetcher(_url: str, _timeout: float) -> bytes:
        return bad_payload

    got = RssHabrIngestion(
        settings=settings,
        store=SeenArticleStore(state),
        fetcher=fetcher,
    ).fetch_new()
    assert got == []
