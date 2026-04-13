from __future__ import annotations

from habr_tech_radar.ingestion.normalize import (
    canonical_habr_http_url,
    normalize_article_identity,
    stable_article_id_from_url,
)


def test_canonical_habr_http_url_strips_tracking_and_fragment() -> None:
    u = "http://www.Habr.com/ru/articles/999/?utm_source=x&foo=bar#frag"
    assert canonical_habr_http_url(u) == "https://habr.com/ru/articles/999/?foo=bar"


def test_stable_article_id_prefers_numeric_slug() -> None:
    c = "https://habr.com/ru/articles/42/"
    assert stable_article_id_from_url(c) == "habr:article:42"


def test_normalize_article_identity() -> None:
    url, sid = normalize_article_identity(
        link="https://habr.com/ru/articles/123456/?utm_campaign=z",
    )
    assert sid == "habr:article:123456"
    assert "utm_" not in url
