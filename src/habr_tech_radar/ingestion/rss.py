from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from habr_tech_radar.ingestion.normalize import normalize_article_identity
from habr_tech_radar.models.article import Article
from habr_tech_radar.state.seen_store import SeenArticleStore

if TYPE_CHECKING:
    from habr_tech_radar.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RssIngestionMetrics:
    feeds_configured: int
    feeds_fetched_ok: int
    items_parsed_total: int
    items_after_cross_feed_dedup: int
    items_new: int
    items_skipped_seen: int


_USER_AGENT = "habr-tech-radar/0.1.0 (+https://github.com/)"
_TAG_RE = re.compile(r"<[^>]+>")
_SUMMARY_MAX_LEN = 8000


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", maxsplit=1)[-1]
    return tag


def _child_text(parent: ET.Element, name: str) -> str | None:
    for child in parent:
        if _local_tag(child.tag) == name:
            parts = [child.text or ""]
            for sub in child:
                parts.append(ET.tostring(sub, encoding="unicode"))
            parts.append(child.tail or "")
            return "".join(parts).strip()
    return None


def _strip_html_to_text(raw: str) -> str:
    t = _TAG_RE.sub(" ", raw)
    t = html.unescape(t)
    return " ".join(t.split())


def _parse_pub_date(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(UTC)
    s = raw.strip()
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        iso = s.replace("Z", "+00:00")
        if "T" not in iso and len(iso) >= 10:
            iso = iso.replace(" ", "T", 1)
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            return datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _iter_items(root: ET.Element) -> Iterable[ET.Element]:
    for elem in root.iter():
        if _local_tag(elem.tag) == "item":
            yield elem


def _categories(item: ET.Element) -> list[str]:
    out: list[str] = []
    for child in item:
        if _local_tag(child.tag) == "category" and child.text and child.text.strip():
            out.append(child.text.strip())
    return out


def parse_rss_bytes(data: bytes, *, feed_url: str) -> list[Article]:
    """Parse RSS 2.0 bytes into Article models. Skips invalid items with warnings."""
    articles: list[Article] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        logger.warning("rss: XML parse error for feed %s: %s", feed_url, e)
        return []

    for item in _iter_items(root):
        try:
            title = (_child_text(item, "title") or "").strip()
            link = (_child_text(item, "link") or "").strip()
            guid_raw = _child_text(item, "guid")
            desc = _child_text(item, "description")
            pub_raw = _child_text(item, "pubDate")
            author = _child_text(item, "author") or _child_text(item, "creator")
            if author:
                author = author.strip()

            if not title:
                logger.warning(
                    "rss: skipping item without title in feed %s",
                    feed_url,
                )
                continue
            if not link:
                logger.warning(
                    "rss: skipping item without link in feed %s",
                    feed_url,
                )
                continue

            canon_url, stable_id = normalize_article_identity(link=link)
            summary: str | None = None
            if desc:
                summary = _strip_html_to_text(desc)
                if len(summary) > _SUMMARY_MAX_LEN:
                    summary = summary[:_SUMMARY_MAX_LEN] + "…"

            meta: dict[str, Any] = {"feed_url": feed_url}
            if guid_raw:
                meta["guid"] = guid_raw.strip()
            meta["canonical_url"] = canon_url
            if stable_id != canon_url:
                meta["stable_id_source"] = "habr_article_num"
            cats = _categories(item)
            if cats:
                meta["categories"] = cats
            if author:
                meta["author"] = author

            art = Article.model_validate(
                {
                    "id": stable_id,
                    "title": title,
                    "url": canon_url,
                    "published_at": _parse_pub_date(pub_raw),
                    "summary": summary,
                    "metadata": meta,
                }
            )
            articles.append(art)
        except Exception as e:  # noqa: BLE001 — defensive per-item
            logger.warning("rss: skipping malformed item in %s: %s", feed_url, e)

    return articles


def _default_fetch(url: str, timeout: float) -> bytes:
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — intentional URL fetch
        return cast(bytes, resp.read())


class RssHabrIngestion:
    """Fetch Habr (or compatible) RSS feeds and return only articles not yet seen."""

    def __init__(
        self,
        *,
        settings: Settings,
        store: SeenArticleStore,
        fetcher: Callable[[str, float], bytes] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._fetcher = fetcher
        self.last_metrics: RssIngestionMetrics | None = None

    def fetch_new(self) -> list[Article]:
        urls = list(self._settings.habr_rss_urls)
        if not urls:
            logger.info("ingestion: no HTR_HABR_RSS_URLS configured, returning no articles")
            self.last_metrics = RssIngestionMetrics(0, 0, 0, 0, 0, 0)
            return []

        by_id: dict[str, Article] = {}
        timeout = self._settings.rss_fetch_timeout_seconds
        feeds_ok = 0
        items_parsed_total = 0

        for feed_url in urls:
            try:
                body = (
                    self._fetcher(feed_url, timeout)
                    if self._fetcher is not None
                    else _default_fetch(feed_url, timeout)
                )
            except HTTPError as e:
                logger.error(
                    "ingestion: HTTP error fetching RSS %s: %s %s",
                    feed_url,
                    e.code,
                    e.reason,
                )
                continue
            except URLError as e:
                logger.error("ingestion: network error fetching RSS %s: %s", feed_url, e.reason)
                continue
            except OSError as e:
                logger.error("ingestion: I/O error fetching RSS %s: %s", feed_url, e)
                continue

            feeds_ok += 1
            parsed = parse_rss_bytes(body, feed_url=feed_url)
            items_parsed_total += len(parsed)
            logger.info(
                "ingestion: feed ok url=%s items_parsed=%d",
                feed_url,
                len(parsed),
            )
            for art in parsed:
                prev = by_id.get(art.id)
                if prev is None:
                    by_id[art.id] = art
                elif prev.metadata.get("feed_url") != art.metadata.get("feed_url"):
                    logger.info(
                        "ingestion: duplicate stable_id=%s kept_first_feed=%s drop_feed=%s",
                        art.id[:80],
                        prev.metadata.get("feed_url"),
                        art.metadata.get("feed_url"),
                    )

        candidates = list(by_id.values())
        seen_before = sum(1 for a in candidates if self._store.is_seen(a.id))
        new_articles = [a for a in candidates if not self._store.is_seen(a.id)]
        if new_articles:
            self._store.mark_seen(a.id for a in new_articles)
            self._store.save()
        self.last_metrics = RssIngestionMetrics(
            feeds_configured=len(urls),
            feeds_fetched_ok=feeds_ok,
            items_parsed_total=items_parsed_total,
            items_after_cross_feed_dedup=len(candidates),
            items_new=len(new_articles),
            items_skipped_seen=seen_before,
        )
        logger.info(
            "ingestion: summary feeds=%d/%d parsed_items=%d unique=%d new=%d skipped_seen=%d",
            feeds_ok,
            len(urls),
            items_parsed_total,
            len(candidates),
            len(new_articles),
            seen_before,
        )
        return new_articles
