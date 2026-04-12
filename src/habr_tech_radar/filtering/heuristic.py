from __future__ import annotations

import logging

from habr_tech_radar.models.article import Article, FilterResult
from habr_tech_radar.settings import Settings, parse_comma_separated_list

logger = logging.getLogger(__name__)


def article_categories(article: Article) -> list[str]:
    """Hub/tag strings from RSS `metadata['categories']`; robust when missing."""
    raw = article.metadata.get("categories")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if isinstance(x, str):
            s = x.strip()
            if s:
                out.append(s)
    return out


def build_search_haystack(article: Article) -> str:
    """Casefolded text used for substring rules (title, summary, categories)."""
    parts: list[str] = [article.title, article.summary or ""]
    parts.extend(article_categories(article))
    return " ".join(parts).casefold()


def _first_matching_term(haystack: str, terms: list[str]) -> str | None:
    for t in terms:
        needle = t.casefold().strip()
        if needle and needle in haystack:
            return t.strip()
    return None


def _category_matches_term(categories: list[str], term: str) -> bool:
    t = term.casefold().strip()
    if not t:
        return False
    return any(t in c.casefold() for c in categories)


class HeuristicArticleFilter:
    """Deterministic substring filter: excludes reject; optional include OR-gate."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._include_keywords = parse_comma_separated_list(settings.include_keywords)
        self._exclude_keywords = parse_comma_separated_list(settings.exclude_keywords)
        self._include_hubs = parse_comma_separated_list(settings.include_hubs)
        self._exclude_hubs = parse_comma_separated_list(settings.exclude_hubs)

    def filter(self, articles: list[Article]) -> list[FilterResult]:
        out: list[FilterResult] = []
        for article in articles:
            fr = self._evaluate(article)
            out.append(fr)
        logger.info("filtering: heuristic evaluated %d article(s)", len(out))
        return out

    def _evaluate(self, article: Article) -> FilterResult:
        haystack = build_search_haystack(article)
        categories = article_categories(article)

        ex_kw = _first_matching_term(haystack, self._exclude_keywords)
        if ex_kw is not None:
            return FilterResult(
                article=article,
                passed=False,
                reason=f"exclude keyword matched: {ex_kw!r}",
            )

        for hub_term in self._exclude_hubs:
            if _category_matches_term(categories, hub_term) or _first_matching_term(
                haystack, [hub_term]
            ):
                return FilterResult(
                    article=article,
                    passed=False,
                    reason=f"exclude hub matched: {hub_term.strip()!r}",
                )

        has_include_rules = bool(self._include_keywords) or bool(self._include_hubs)
        if not has_include_rules:
            return FilterResult(
                article=article,
                passed=True,
                reason="permissive (no include rules)",
            )

        in_kw = _first_matching_term(haystack, self._include_keywords)
        if in_kw is not None:
            return FilterResult(
                article=article,
                passed=True,
                reason=f"include keyword matched: {in_kw!r}",
            )

        for hub_term in self._include_hubs:
            if _category_matches_term(categories, hub_term):
                return FilterResult(
                    article=article,
                    passed=True,
                    reason=f"include hub matched: {hub_term.strip()!r}",
                )
            if _first_matching_term(haystack, [hub_term]) is not None:
                return FilterResult(
                    article=article,
                    passed=True,
                    reason=f"include hub matched (text): {hub_term.strip()!r}",
                )

        return FilterResult(
            article=article,
            passed=False,
            reason="no include keyword/hub match",
        )
