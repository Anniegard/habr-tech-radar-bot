from __future__ import annotations

import html
import json
import logging
import re
from datetime import UTC, datetime
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from habr_tech_radar.filtering.heuristic import article_categories, build_search_haystack
from habr_tech_radar.models.article import ArticleScore, FilterResult, ScoreExplanation
from habr_tech_radar.settings import (
    Settings,
    effective_recency_max_points,
    parse_comma_separated_list,
)

logger = logging.getLogger(__name__)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_USER_AGENT = "habr-tech-radar/0.1.0 (+https://github.com/Anniegard/habr-tech-radar-bot)"
_KEYWORD_SCORE_MAX = 50
_LLM_SCORE_MAX = 50
_TOTAL_SCORE_MAX = 100


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


def _clamp_int(v: int, *, low: int, high: int) -> int:
    return max(low, min(v, high))


def _strip_html_to_text(raw: str) -> str:
    txt = _HTML_TAG_RE.sub(" ", raw)
    txt = html.unescape(txt)
    return " ".join(txt.split())


def _extract_article_text(html_body: str) -> str:
    marker = '<div class="tm-article-body'
    start = html_body.find(marker)
    if start < 0:
        start = html_body.find("<article")
    if start < 0:
        start = 0
    sliced = html_body[start:]
    return _strip_html_to_text(sliced)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return "…"
    return text[: max_chars - 1].rstrip() + "…"


def _fetch_article_text(url: str, timeout: float) -> str:
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = cast(bytes, resp.read()).decode("utf-8", errors="replace")
    return _extract_article_text(body)


def _parse_llm_scores(raw: str) -> tuple[int, str | None]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be JSON object")
    required = (
        "practical_value",
        "novelty",
        "depth",
        "signal_to_noise",
        "relevance_to_tech_radar",
    )
    values: list[int] = []
    for key in required:
        v = payload.get(key)
        if not isinstance(v, int):
            raise ValueError(f"{key} must be int")
        if v < 0 or v > 10:
            raise ValueError(f"{key} must be in 0..10")
        values.append(v)
    total = sum(values)
    provided_total = payload.get("total")
    if isinstance(provided_total, int) and provided_total != total:
        logger.warning("scoring: llm provided total mismatch, using computed sum")
    reason = payload.get("short_reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("short_reason must be string")
    return _clamp_int(total, low=0, high=_LLM_SCORE_MAX), reason


def _build_llm_context(*, fr: FilterResult, body_text: str | None, max_summary_chars: int) -> str:
    article = fr.article
    summary = _truncate(article.summary or "", max_summary_chars)
    categories = ", ".join(article_categories(article))
    author = str(article.metadata.get("author", "")).strip()
    parts: list[str] = [
        f"Title: {article.title}",
        f"Summary: {summary}",
        f"Categories: {categories}",
        f"Author: {author}",
    ]
    if body_text:
        parts.append(f"Body:\n{body_text}")
    context = "\n".join(parts).strip()
    return context


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

        keyword_points = _clamp_int(max(0, raw), low=0, high=_KEYWORD_SCORE_MAX)
        llm_points, llm_applied, llm_reason, fetch_used = self._score_llm(
            fr=fr, keyword_points=keyword_points
        )
        total_points = _clamp_int(keyword_points + llm_points, low=0, high=_TOTAL_SCORE_MAX)

        selection_summary = _selection_summary(matched_s, matched_t, matched_i, matched_hubs)

        expl = ScoreExplanation(
            matched_include_keywords=matched_i,
            matched_exclude_keywords=[],
            matched_strong_keywords=matched_s,
            matched_technical_keywords=matched_t,
            matched_negative_keywords=matched_neg,
            matched_include_hubs=matched_hubs,
            breakdown=breakdown,
            selection_summary=selection_summary,
            keyword_points=keyword_points,
            llm_points=llm_points,
            total_points=total_points,
            llm_applied=llm_applied,
            llm_fallback_reason=llm_reason,
            content_fetch_used=fetch_used,
        )

        reasons = _build_reason_lines(
            points=total_points,
            raw=raw,
            selection_summary=selection_summary,
            matched_neg=matched_neg,
            matched_hubs=matched_hubs,
            keyword_points=keyword_points,
            llm_points=llm_points,
            llm_reason=llm_reason,
        )

        return ArticleScore(
            article=article,
            points=total_points,
            explanation=expl,
            reasons=reasons,
        )

    def _score_llm(
        self, *, fr: FilterResult, keyword_points: int
    ) -> tuple[int, bool, str | None, bool]:
        settings = self._settings
        if keyword_points < settings.llm_keyword_threshold:
            return 0, False, "below_keyword_threshold", False
        if not settings.llm_scoring_enabled:
            return 0, False, "llm_disabled", False
        if not settings.openai_api_key:
            return 0, False, "missing_api_key", False

        article = fr.article
        content_fetch_used = False
        article_text: str | None = None
        if settings.llm_fetch_article_enabled:
            try:
                article_text = _fetch_article_text(
                    str(article.url), timeout=settings.llm_fetch_article_timeout_seconds
                )
                article_text = _truncate(article_text, settings.llm_max_article_chars)
                content_fetch_used = True
            except (HTTPError, URLError, OSError, UnicodeDecodeError, ValueError) as e:
                logger.warning("scoring: failed to fetch article text id=%s err=%s", article.id, e)
        llm_context = _build_llm_context(
            fr=fr,
            body_text=article_text,
            max_summary_chars=settings.llm_max_summary_chars,
        )
        if not llm_context:
            return 0, False, "fallback_context_unavailable", content_fetch_used

        prompt = (
            "Evaluate this Habr article for a personal tech radar.\n"
            "Return strict JSON only with integer fields 0..10:\n"
            "practical_value, novelty, depth, signal_to_noise, "
            "relevance_to_tech_radar, total, short_reason.\n"
            "No markdown, no prose around JSON.\n\n"
            f"{llm_context}"
        )
        request_body = json.dumps(
            {
                "model": settings.llm_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a strict scoring engine for a personal tech radar. "
                            "Always return JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode("utf-8")
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=request_body,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=settings.llm_request_timeout_seconds) as resp:  # noqa: S310
                body = cast(bytes, resp.read()).decode("utf-8", errors="replace")
            outer = json.loads(body)
            if not isinstance(outer, dict):
                raise ValueError("invalid LLM completion payload")
            choices = outer.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("missing choices")
            choice0 = choices[0]
            if not isinstance(choice0, dict):
                raise ValueError("invalid first choice")
            msg = choice0.get("message")
            if not isinstance(msg, dict):
                raise ValueError("missing message")
            content = msg.get("content")
            if not isinstance(content, str):
                raise ValueError("missing content")
            llm_points, _short_reason = _parse_llm_scores(content)
            return llm_points, True, None, content_fetch_used
        except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as e:
            logger.warning("scoring: llm fallback id=%s err=%s", article.id, e)
            return 0, False, "llm_request_or_parse_failed", content_fetch_used


def _build_reason_lines(
    *,
    points: int,
    raw: int,
    selection_summary: str | None,
    matched_neg: list[str],
    matched_hubs: list[str],
    keyword_points: int,
    llm_points: int,
    llm_reason: str | None,
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
    if raw != keyword_points:
        lines.append(f"Keyword score: {keyword_points} (raw was {raw})")
    else:
        lines.append(f"Keyword score: {keyword_points}")
    lines.append(f"LLM score: {llm_points}")
    lines.append(f"Total score: {points}")
    if llm_reason:
        lines.append(f"LLM fallback: {llm_reason}")
    return lines
