"""Aggregator orchestration: rank live offers, then attach grounded LLM reasons.

Search (the live SerpApi call) is injected by the caller (API) so this stays testable offline
and search-free.

**Cost + honesty controls (Decisions 20, 21).** SerpApi is *metered* (free plan = 250 searches a
month), which makes it the binding constraint on the whole product — not compute. Two rules
follow, and they were both violated before:

1. **A global budget guard.** Per-user rate limits are not enough: one user inside their own
   quota could drain the entire monthly allowance for everybody. Spend is therefore counted
   globally in Redis (per day and per month) and refused past the cap.
2. **A dead source is NOT "no match".** Previously any failure (quota exhausted, bad key,
   network) returned ``no_match=True`` — an outage that looked exactly like a legitimate empty
   result, so nobody could tell the product was broken. Failures now return
   ``source_unavailable=True`` with a reason, which is a distinct, alertable state.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter

from core.cache import (
    CACHE_HITS,
    CACHE_MISSES,
    RedisCache,
    get_catalog_version,
    hash_key,
    normalize_query,
)
from core.config import get_settings
from core.llm import explain_offers
from core.models import AggregatorResult, ExplanationSet, Offer, RankedOffer
from recommender.offer_ranking import rank_offers
from recommender.ranking import RankingConfig
from sources.serpapi_source import search_offers

logger = logging.getLogger("p2.aggregator")

# Cache the whole result (offers + reasons) so a repeat query costs 0 SerpApi searches AND
# 0 LLM calls within the window. This is the key cost control for the metered SerpApi quota.
# 6h (not 10min): shopping offers are not volatile, and every expiry costs real money.
AGGREGATE_TTL_SECONDS = 6 * 3600

SEARCH_SPEND = Counter("serpapi_searches_total", "Live SerpApi searches actually spent")
SOURCE_UNAVAILABLE = Counter(
    "source_unavailable_total", "Aggregator degraded responses", ["reason"]
)

_DAY_KEY = "serpapi:spend:day:{day}"
_MONTH_KEY = "serpapi:spend:month:{month}"


def _budget_keys(now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now(UTC)
    return (
        _DAY_KEY.format(day=now.strftime("%Y-%m-%d")),
        _MONTH_KEY.format(month=now.strftime("%Y-%m")),
    )


def budget_exceeded(cache: RedisCache) -> str:
    """Return a reason string if the global SerpApi budget is spent, else ''."""
    settings = get_settings()
    day_key, month_key = _budget_keys()
    if settings.serpapi_daily_budget:
        spent_today = int(cache.get(day_key) or 0)
        if spent_today >= settings.serpapi_daily_budget:
            return f"daily search budget reached ({spent_today}/{settings.serpapi_daily_budget})"
    if settings.serpapi_monthly_budget:
        spent_month = int(cache.get(month_key) or 0)
        if spent_month >= settings.serpapi_monthly_budget:
            return (
                f"monthly search budget reached ({spent_month}/{settings.serpapi_monthly_budget})"
            )
    return ""


def record_search_spend(cache: RedisCache) -> None:
    """Count one live search against the global day/month budget."""
    day_key, month_key = _budget_keys()
    cache.incr(day_key, ttl_seconds=2 * 24 * 3600)
    cache.incr(month_key, ttl_seconds=40 * 24 * 3600)
    SEARCH_SPEND.inc()


def _degraded(query: str, reason: str, detail: str) -> AggregatorResult:
    SOURCE_UNAVAILABLE.labels(reason).inc()
    return AggregatorResult(
        query=query, offers=[], no_match=False, source_unavailable=True, detail=detail
    )


def merge_offer_reasons(
    offers: list[RankedOffer], explanations: ExplanationSet
) -> list[RankedOffer]:
    reason_by_id = {e.product_id: e.reason for e in explanations.explanations}
    return [
        ranked.model_copy(update={"reason": reason_by_id.get(ranked.offer.product_id, "")})
        for ranked in offers
    ]


def rank_and_explain(
    query: str,
    offers: list[Offer],
    model: Any,
    *,
    k: int = 5,
    config: RankingConfig | None = None,
    callbacks: list[Any] | None = None,
) -> AggregatorResult:
    """Rank offers, keep top-k, attach grounded reasons. No live search happens here."""
    ranked = rank_offers(offers, config)[:k]
    if not ranked:
        return AggregatorResult(query=query, offers=[], no_match=True)
    explanations = explain_offers(query, ranked, model, callbacks)
    return AggregatorResult(
        query=query,
        summary=explanations.summary,
        offers=merge_offer_reasons(ranked, explanations),
        no_match=False,
    )


def aggregate_stream(
    query: str,
    cache: RedisCache,
    model: Any,
    *,
    k: int = 5,
    num: int = 10,
    config: RankingConfig | None = None,
    callbacks: list[Any] | None = None,
    search_fn: Callable[[str, int], list[Offer]] | None = None,
) -> Iterator[tuple[str, AggregatorResult]]:
    """Staged aggregation, so the UI can show CARDS before the LLM has written its reasons.

    Yields ``("offers", partial)`` — ranked offers, no reasons yet — then ``("final", full)``.

    The blocking version made the user wait for search **and** the LLM before anything appeared
    (measured cold: 2.94s, which breached the p95 < 2s NFR). Ranking is done as soon as the search
    returns, so the cards can be painted ~1-1.5s earlier while the explanations are still being
    generated. On a cache hit only ``("final", ...)`` is emitted — there is nothing to wait for.
    """
    search = search_fn if search_fn is not None else (lambda q, n: search_offers(q, num=n))
    version = get_catalog_version(cache)
    key = "agg:" + hash_key(version, str(k), normalize_query(query))

    cached = cache.get_json(key)
    if cached is not None:
        CACHE_HITS.labels("aggregate").inc()
        yield "final", AggregatorResult.model_validate(cached)
        return
    CACHE_MISSES.labels("aggregate").inc()

    # Global budget guard — a cache miss is about to spend real money.
    reason = budget_exceeded(cache)
    if reason:
        logger.error("SerpApi budget exhausted: %s", reason)
        yield (
            "final",
            _degraded(
                query,
                "budget_exhausted",
                "Live product search is temporarily unavailable (search budget reached). "
                "Please try again later.",
            ),
        )
        return

    try:
        offers = search(query, num)
        record_search_spend(cache)
    except Exception:
        # A dead source is an OUTAGE, not an empty result. Never report it as no_match.
        logger.error("shopping source failed; serving degraded response", exc_info=True)
        yield (
            "final",
            _degraded(
                query,
                "source_error",
                "Live product search is temporarily unavailable. Please try again shortly.",
            ),
        )
        return

    ranked = rank_offers(offers, config)[:k]
    if not ranked:
        yield "final", AggregatorResult(query=query, offers=[], no_match=True)
        return

    # Cards first — the expensive LLM call has not happened yet.
    yield "offers", AggregatorResult(query=query, offers=ranked, no_match=False)

    explanations = explain_offers(query, ranked, model, callbacks)
    result = AggregatorResult(
        query=query,
        summary=explanations.summary,
        offers=merge_offer_reasons(ranked, explanations),
        no_match=False,
    )
    cache.set_json(key, result.model_dump(), AGGREGATE_TTL_SECONDS)
    yield "final", result


def aggregate(
    query: str,
    cache: RedisCache,
    model: Any,
    *,
    k: int = 5,
    num: int = 10,
    config: RankingConfig | None = None,
    callbacks: list[Any] | None = None,
    search_fn: Callable[[str, int], list[Offer]] | None = None,
) -> AggregatorResult:
    """Blocking aggregation (kept for the non-streaming /aggregate endpoint + tests).

    Cache-hit -> 0 SerpApi/LLM; miss -> 1 search + rank + explain. ``search_fn`` (the live SerpApi
    call) is injected so tests run offline and search-free.
    """
    final = AggregatorResult(query=query, offers=[], no_match=True)
    for stage, result in aggregate_stream(
        query,
        cache,
        model,
        k=k,
        num=num,
        config=config,
        callbacks=callbacks,
        search_fn=search_fn,
    ):
        if stage == "final":
            final = result
    return final
