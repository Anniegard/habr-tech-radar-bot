from __future__ import annotations

import html
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from habr_tech_radar.models.article import RadarItem

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
_TRUNCATION_SUFFIX = "\n\n… (truncated)"
_PROD_SUMMARY_MAX_CHARS = 450

_BREAKDOWN_LABELS: dict[str, str] = {
    "include_keywords": "Include keywords",
    "strong_keywords": "Strong signals",
    "technical_signals": "Technical signals",
    "include_hubs": "Hubs",
    "title_match_bonus": "Title bonus",
    "recency": "Recency",
    "penalties": "Penalties",
}


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


def _fmt_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    pub = dt
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=UTC)
    pub_utc = pub.astimezone(UTC)
    return pub_utc.strftime("%Y-%m-%d %H:%M UTC")


def _truncate_plain(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len < 2:
        return "…"
    return text[: max_len - 1].rstrip() + "…"


def _fmt_breakdown_value(key: str, pts: int) -> str:
    label = _BREAKDOWN_LABELS.get(key, key.replace("_", " ").title())
    if pts < 0:
        return f"{html.escape(label, quote=False)}: {pts}"
    return f"{html.escape(label, quote=False)}: +{pts}"


def format_radar_item_html(item: RadarItem, *, format_mode: str = "prod") -> str:
    """Render one RadarItem as Telegram HTML (escape all user/content-derived text)."""
    mode = format_mode.casefold().strip()
    if mode in ("prod", "production"):
        return _format_prod(item)
    if mode in ("debug", "dev"):
        return _format_debug(item)
    return _format_prod(item)


def _format_prod(item: RadarItem) -> str:
    article = item.score.article
    expl = item.score.explanation
    title = html.escape(article.title, quote=False)
    url_raw = str(article.url)
    url_clean = strip_tracking_query_params(url_raw)
    href = html.escape(url_clean, quote=True)
    display_link = html.escape(url_clean, quote=False)

    lines: list[str] = [
        "<b>Habr Tech Radar</b>",
        "",
        f"<b>{title}</b>",
        "",
        f"<b>Score:</b> {item.score.points}",
    ]

    t = _fmt_utc(article.published_at)
    if t:
        lines.append(f"<b>Published:</b> {html.escape(t, quote=False)}")

    why = expl.selection_summary
    if why:
        lines.extend(["", f"<b>Почему выбрано:</b> {html.escape(why, quote=False)}"])

    if article.summary:
        short = _truncate_plain(article.summary, _PROD_SUMMARY_MAX_CHARS)
        lines.extend(["", f"<b>Коротко:</b> {html.escape(short, quote=False)}"])

    lines.extend(["", f'<b>Ссылка:</b> <a href="{href}">{display_link}</a>'])

    if item.enriched_summary:
        en = _truncate_plain(item.enriched_summary, _PROD_SUMMARY_MAX_CHARS)
        lines.extend(["", f"<b>Enriched:</b> {html.escape(en, quote=False)}"])

    return "\n".join(lines).strip()


def _format_debug(item: RadarItem) -> str:
    article = item.score.article
    expl = item.score.explanation
    title = html.escape(article.title, quote=False)
    url_raw = str(article.url)
    url_clean = strip_tracking_query_params(url_raw)
    href = html.escape(url_clean, quote=True)
    display_link = html.escape(url_clean, quote=False)

    keyword_max = 50
    llm_max = 50
    total_max = 100
    lines: list[str] = [
        "<b>Habr Tech Radar</b> <i>(debug)</i>",
        "",
        f"<b>{title}</b>",
        "",
        f"<b>Keyword score:</b> {expl.keyword_points}/{keyword_max}",
        f"<b>LLM score:</b> {expl.llm_points}/{llm_max}",
        f"<b>Total score:</b> {expl.total_points or item.score.points}/{total_max}",
    ]

    t = _fmt_utc(article.published_at)
    if t:
        lines.append(f"<b>Published:</b> {html.escape(t, quote=False)}")

    lines.extend(["", f'<b>Link:</b> <a href="{href}">{display_link}</a>'])

    if expl.selection_summary:
        lines.extend(["", "<b>Why (summary)</b>", html.escape(expl.selection_summary, quote=False)])

    sig_lines: list[str] = []
    if expl.matched_strong_keywords:
        kws = ", ".join(html.escape(k, quote=False) for k in expl.matched_strong_keywords)
        sig_lines.append(f"<b>Strong:</b> {kws}")
    if expl.matched_technical_keywords:
        kws = ", ".join(html.escape(k, quote=False) for k in expl.matched_technical_keywords)
        sig_lines.append(f"<b>Technical:</b> {kws}")
    if expl.matched_include_keywords:
        kws = ", ".join(html.escape(k, quote=False) for k in expl.matched_include_keywords)
        sig_lines.append(f"<b>Include:</b> {kws}")
    if expl.matched_include_hubs:
        hubs = ", ".join(html.escape(h, quote=False) for h in expl.matched_include_hubs)
        sig_lines.append(f"<b>Hubs:</b> {hubs}")
    if expl.matched_negative_keywords:
        kws = ", ".join(html.escape(k, quote=False) for k in expl.matched_negative_keywords)
        sig_lines.append(f"<b>Negative / noise:</b> {kws}")
    if sig_lines:
        lines.extend(["", "<b>Matched signals</b>", ""])
        lines.extend(sig_lines)

    if expl.breakdown:
        lines.extend(["", "<b>Score breakdown</b>", ""])
        for key, pts in sorted(expl.breakdown.items()):
            lines.append(_fmt_breakdown_value(key, pts))

    if item.score.reasons:
        lines.extend(["", "<b>Notes</b>", ""])
        for r in item.score.reasons:
            lines.append(html.escape(r, quote=False))

    if article.summary:
        lines.extend(["", "<b>Summary</b>", html.escape(article.summary, quote=False)])

    if item.enriched_summary:
        lines.extend(["", "<b>Enriched</b>", html.escape(item.enriched_summary, quote=False)])

    return "\n".join(lines).strip()


def truncate_for_telegram(
    text: str,
    *,
    max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> tuple[str, bool]:
    """If text exceeds Telegram limit, truncate and return (text, True)."""
    if len(text) <= max_len:
        return text, False
    budget = max_len - len(_TRUNCATION_SUFFIX)
    if budget < 1:
        return _TRUNCATION_SUFFIX.strip(), True
    return text[:budget] + _TRUNCATION_SUFFIX, True
