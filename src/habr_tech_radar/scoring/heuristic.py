from __future__ import annotations

import logging
from datetime import UTC, datetime

from habr_tech_radar.filtering.heuristic import article_categories, build_search_haystack
from habr_tech_radar.models.article import ArticleScore, FilterResult, ScoreExplanation
from habr_tech_radar.settings import Settings, parse_comma_separated_list

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


class HeuristicArticleScoring:
    """Integer score from keyword/hub weights, title bonus, and recency."""

    def __init__(
        self,
        settings: Settings,
        *,
        reference_time: datetime | None = None,
    ) -> None:
        self._settings = settings
        self._include_keywords = parse_comma_separated_list(settings.include_keywords)
        self._include_hubs = parse_comma_separated_list(settings.include_hubs)
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

        matched_kw = _matching_keywords(haystack_cf, self._include_keywords)
        matched_hubs = _matching_hubs_in_categories(categories, self._include_hubs)

        breakdown: dict[str, int] = {}
        points = 0

        w_kw = self._settings.score_weight_include_keyword
        for _ in matched_kw:
            breakdown["include_keywords"] = breakdown.get("include_keywords", 0) + w_kw
            points += w_kw

        w_hub = self._settings.score_weight_include_hub
        for _ in matched_hubs:
            breakdown["include_hubs"] = breakdown.get("include_hubs", 0) + w_hub
            points += w_hub

        w_title = self._settings.score_weight_title_match_bonus
        for kw in matched_kw:
            if kw.casefold().strip() in title_cf:
                breakdown["title_match_bonus"] = breakdown.get("title_match_bonus", 0) + w_title
                points += w_title

        rec = _recency_points(
            article.published_at,
            self._reference_time,
            max_points=self._settings.score_weight_recency_max,
            window_days=self._settings.score_recency_window_days,
        )
        if self._settings.score_weight_recency_max > 0:
            breakdown["recency"] = rec
        points += rec

        expl = ScoreExplanation(
            matched_include_keywords=matched_kw,
            matched_exclude_keywords=[],
            matched_include_hubs=matched_hubs,
            breakdown=breakdown,
        )
        reasons = [
            f"points={points}",
            f"breakdown={breakdown}",
        ]
        return ArticleScore(article=article, points=points, explanation=expl, reasons=reasons)
