from __future__ import annotations

import logging
from datetime import UTC, datetime

from habr_tech_radar.filtering.heuristic import article_categories, build_search_haystack
from habr_tech_radar.models.article import ArticleScore, FilterResult, ScoreExplanation
from habr_tech_radar.settings import (
    Settings,
    effective_recency_max_points,
    parse_comma_separated_list,
)

logger = logging.getLogger(__name__)


def _recency_points(
    published_at: datetime,
    reference_time: datetime,
    *,
    max_points: int,
    window_days: float,
) -> int:
    if max_points <= 0 or window_days <= 0:
        return 0
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=UTC)
    ref = reference_time
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    delta = ref - pub.astimezone(UTC)
    days = max(0.0, delta.total_seconds() / 86400.0)
    frac = max(0.0, 1.0 - min(days / window_days, 1.0))
    return int(max_points * frac)


def _matching_keywords(haystack_cf: str, keywords: list[str]) -> list[str]:
    found: list[str] = []
    for kw in keywords:
        needle = kw.casefold().strip()
        if needle and needle in haystack_cf:
            found.append(kw.strip())
    return found


def _matching_hubs_in_categories(categories: list[str], hubs: list[str]) -> list[str]:
    cats_cf = [c.casefold() for c in categories]
    matched: list[str] = []
    for hub in hubs:
        h = hub.casefold().strip()
        if not h:
            continue
        for c in cats_cf:
            if h in c:
                matched.append(hub.strip())
                break
    return matched


def _tiered_keyword_matches(
    haystack_cf: str,
    strong: list[str],
    technical: list[str],
    include: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Strong > technical > include; a phrase only contributes in the highest tier."""
    matched_strong = _matching_keywords(haystack_cf, strong)
    strong_needles = {k.casefold().strip() for k in matched_strong}

    matched_technical: list[str] = []
    for kw in technical:
        needle = kw.casefold().strip()
        if not needle or needle not in haystack_cf:
            continue
        if needle in strong_needles:
            continue
        matched_technical.append(kw.strip())

    tech_needles = {k.casefold().strip() for k in matched_technical}
    consumed = strong_needles | tech_needles

    matched_include: list[str] = []
    for kw in include:
        needle = kw.casefold().strip()
        if not needle or needle not in haystack_cf:
            continue
        if needle in consumed:
            continue
        matched_include.append(kw.strip())

    return matched_strong, matched_technical, matched_include


def _title_match_bonus(
    title_cf: str,
    keywords: list[str],
    *,
    bonus: int,
    breakdown: dict[str, int],
) -> int:
    extra = 0
    for kw in keywords:
        if kw.casefold().strip() in title_cf:
            breakdown["title_match_bonus"] = breakdown.get("title_match_bonus", 0) + bonus
            extra += bonus
    return extra


def _selection_summary(
    matched_strong: list[str],
    matched_technical: list[str],
    matched_include: list[str],
    matched_hubs: list[str],
    *,
    max_terms: int = 12,
) -> str | None:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in (matched_strong, matched_technical, matched_include, matched_hubs):
        for x in group:
            k = x.casefold().strip()
            if not k or k in seen:
                continue
            seen.add(k)
            ordered.append(x.strip())
            if len(ordered) >= max_terms:
                return ", ".join(ordered)
    return ", ".join(ordered) if ordered else None


class HeuristicArticleScoring:
    """Integer score from tiered keywords, hubs, title bonus, recency, and penalties."""

    def __init__(
        self,
        settings: Settings,
        *,
        reference_time: datetime | None = None,
    ) -> None:
        self._settings = settings
        self._include_keywords = parse_comma_separated_list(settings.include_keywords)
        self._include_hubs = parse_comma_separated_list(settings.include_hubs)
        self._strong_keywords = parse_comma_separated_list(settings.score_strong_keywords)
        self._technical_keywords = parse_comma_separated_list(settings.score_technical_keywords)
        self._negative_keywords = parse_comma_separated_list(settings.score_negative_keywords)
        self._reference_time = reference_time if reference_time is not None else datetime.now(UTC)

    def score(self, filtered: list[FilterResult]) -> list[ArticleScore]:
        scores: list[ArticleScore] = []
        for fr in filtered:
            if not fr.passed:
                continue
            scores.append(self._score_one(fr))
        logger.info("scoring: heuristic scored %d article(s)", len(scores))
        return scores

    def _score_one(self, fr: FilterResult) -> ArticleScore:
        article = fr.article
        haystack_cf = build_search_haystack(article)
        title_cf = article.title.casefold()
        categories = article_categories(article)

        matched_s, matched_t, matched_i = _tiered_keyword_matches(
            haystack_cf,
            self._strong_keywords,
            self._technical_keywords,
            self._include_keywords,
        )
        matched_hubs = _matching_hubs_in_categories(categories, self._include_hubs)
        matched_neg = _matching_keywords(haystack_cf, self._negative_keywords)

        breakdown: dict[str, int] = {}
        raw = 0

        w_inc = self._settings.score_weight_include_keyword
        for _ in matched_i:
            breakdown["include_keywords"] = breakdown.get("include_keywords", 0) + w_inc
            raw += w_inc

        w_str = self._settings.score_weight_strong_keyword
        for _ in matched_s:
            breakdown["strong_keywords"] = breakdown.get("strong_keywords", 0) + w_str
            raw += w_str

        w_tech = self._settings.score_weight_technical_signal
        for _ in matched_t:
            breakdown["technical_signals"] = breakdown.get("technical_signals", 0) + w_tech
            raw += w_tech

        w_hub = self._settings.score_weight_include_hub
        for _ in matched_hubs:
            breakdown["include_hubs"] = breakdown.get("include_hubs", 0) + w_hub
            raw += w_hub

        w_title = self._settings.score_weight_title_match_bonus
        raw += _title_match_bonus(title_cf, matched_i, bonus=w_title, breakdown=breakdown)
        raw += _title_match_bonus(title_cf, matched_s, bonus=w_title, breakdown=breakdown)
        raw += _title_match_bonus(title_cf, matched_t, bonus=w_title, breakdown=breakdown)

        rec_max = effective_recency_max_points(self._settings)
        rec = _recency_points(
            article.published_at,
            self._reference_time,
            max_points=rec_max,
            window_days=self._settings.score_recency_window_days,
        )
        if rec_max > 0:
            breakdown["recency"] = rec
        raw += rec

        pen_w = self._settings.score_weight_penalty_per_hit
        if matched_neg and pen_w > 0:
            pen_total = -(pen_w * len(matched_neg))
            breakdown["penalties"] = pen_total
            raw += pen_total

        points = max(0, raw)

        selection_summary = _selection_summary(matched_s, matched_t, matched_i, matched_hubs)
        if selection_summary is None and rec > 0 and not (matched_s or matched_t or matched_i):
            selection_summary = f"Mostly freshness (recency +{rec})"

        expl = ScoreExplanation(
            matched_include_keywords=matched_i,
            matched_exclude_keywords=[],
            matched_strong_keywords=matched_s,
            matched_technical_keywords=matched_t,
            matched_negative_keywords=matched_neg,
            matched_include_hubs=matched_hubs,
            breakdown=breakdown,
            selection_summary=selection_summary,
        )

        reasons = _build_reason_lines(
            points=points,
            raw=raw,
            selection_summary=selection_summary,
            matched_neg=matched_neg,
            matched_hubs=matched_hubs,
        )

        return ArticleScore(article=article, points=points, explanation=expl, reasons=reasons)


def _build_reason_lines(
    *,
    points: int,
    raw: int,
    selection_summary: str | None,
    matched_neg: list[str],
    matched_hubs: list[str],
) -> list[str]:
    lines: list[str] = []
    if selection_summary:
        lines.append(f"Signals: {selection_summary}")
    elif matched_hubs:
        lines.append(f"Hubs: {', '.join(matched_hubs[:10])}")
    else:
        lines.append("Signals: (recency / penalties only)")
    if matched_neg:
        lines.append(f"Noise matches: {', '.join(matched_neg[:10])}")
    if raw != points:
        lines.append(f"Capped score: {points} (raw was {raw})")
    else:
        lines.append(f"Score: {points}")
    return lines
