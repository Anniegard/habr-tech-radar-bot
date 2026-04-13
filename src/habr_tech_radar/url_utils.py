from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def strip_tracking_query_params(url: str) -> str:
    """Remove utm_* and common tracking query params; keep other query pairs."""
    p = urlparse(url)
    if not p.query:
        return url
    pairs = parse_qs(p.query, keep_blank_values=True)
    kept: dict[str, list[str]] = {}
    for k, vals in pairs.items():
        kl = k.casefold()
        if kl.startswith("utm_") or kl in ("fbclid", "gclid"):
            continue
        kept[k] = vals
    new_query = urlencode(kept, doseq=True) if kept else ""
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))
