from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from habr_tech_radar.url_utils import strip_tracking_query_params

_HABR_ARTICLE_NUM = re.compile(r"/articles/(\d+)/?", re.IGNORECASE)


def canonical_habr_http_url(url: str) -> str:
    """Normalize Habr article URL for dedup: https, no fragment, strip tracking query."""
    raw = url.strip()
    if not raw:
        return raw
    p = urlparse(raw)
    scheme = (p.scheme or "https").casefold()
    if scheme not in ("http", "https"):
        scheme = "https"
    netloc = p.netloc.casefold()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = p.path or "/"
    if path != "/" and not path.endswith("/"):
        path = path + "/"
    if netloc.endswith("habr.com") and scheme == "http":
        scheme = "https"
    cleaned = strip_tracking_query_params(
        urlunparse((scheme, netloc, path, "", p.query, "")),
    )
    p2 = urlparse(cleaned)
    return urlunparse((p2.scheme, p2.netloc, p2.path, "", p2.query, ""))


def stable_article_id_from_url(canonical_url: str) -> str:
    """Stable id for dedup across RSS sources (prefer numeric Habr article id)."""
    m = _HABR_ARTICLE_NUM.search(canonical_url)
    if m:
        return f"habr:article:{m.group(1)}"
    return canonical_url


def normalize_article_identity(*, link: str) -> tuple[str, str]:
    """Return (canonical_url, stable_id)."""
    canon = canonical_habr_http_url(link)
    sid = stable_article_id_from_url(canon)
    return canon, sid
