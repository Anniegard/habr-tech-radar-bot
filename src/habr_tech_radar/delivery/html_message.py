from __future__ import annotations

import html
from datetime import UTC, datetime

from habr_tech_radar.models.article import RadarItem

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
_TRUNCATION_SUFFIX = "\n\n… (truncated)"

_BREAKDOWN_LABELS: dict[str, str] = {
    "include_keywords": "Keywords",
    "include_hubs": "Hubs",
    "title_match_bonus": "Title bonus",
    "recency": "Recency",
}


def _fmt_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    pub = dt
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=UTC)
    pub_utc = pub.astimezone(UTC)
    return pub_utc.strftime("%Y-%m-%d %H:%M UTC")


def format_radar_item_html(item: RadarItem) -> str:
    """Render one RadarItem as Telegram HTML (escape all user/content-derived text)."""
    article = item.score.article
    expl = item.score.explanation
    title = html.escape(article.title, quote=False)
    url_str = str(article.url)
    href = html.escape(url_str, quote=True)
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

    lines.extend(["", f'<b>Link:</b> <a href="{href}">{href}</a>'])

    why_parts: list[str] = []
    if expl.matched_include_keywords:
        kws = ", ".join(html.escape(k, quote=False) for k in expl.matched_include_keywords)
        why_parts.append(f"Include keywords: {kws}")
    if expl.matched_include_hubs:
        hubs = ", ".join(html.escape(h, quote=False) for h in expl.matched_include_hubs)
        why_parts.append(f"Include hubs: {hubs}")
    if expl.breakdown:
        for key, pts in sorted(expl.breakdown.items()):
            label = _BREAKDOWN_LABELS.get(key, key.replace("_", " ").title())
            why_parts.append(f"{html.escape(label, quote=False)}: +{pts}")

    if why_parts:
        lines.extend(["", "<b>Why (score)</b>", ""])
        lines.extend(why_parts)

    if item.score.reasons:
        lines.extend(["", "<b>Notes</b>", ""])
        for r in item.score.reasons:
            lines.append(html.escape(r, quote=False))

    if article.summary:
        lines.extend(["", "<b>Summary</b>", html.escape(article.summary, quote=False)])

    if item.enriched_summary:
        lines.extend(
            ["", "<b>Enriched</b>", html.escape(item.enriched_summary, quote=False)]
        )

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
