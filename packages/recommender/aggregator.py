"""Aggregator orchestration: rank live offers, then attach grounded LLM reasons.

Search (the live SerpApi call) is injected by the caller (API) so this stays testable offline
and search-free.

**Cost + honesty controls.** SerpApi is *metered* (free plan = 250 searches a
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


_DAY_TTL_SECONDS = 2 * 24 * 3600
_MONTH_TTL_SECONDS = 40 * 24 * 3600


def release_search_budget(cache: RedisCache) -> None:
    """Hand back a claim that was never spent (the search failed before going out)."""
    day_key, month_key = _budget_keys()
    cache.decr(day_key)
    cache.decr(month_key)


def reserve_search_budget(cache: RedisCache) -> str:
    """Atomically claim one search against the global day+month budget.

    Returns ``""`` if the claim succeeded — the caller must then either spend it or call
    ``release_search_budget``. Otherwise returns a reason string, having claimed nothing.

    **Why claim first instead of checking first.** This used to read the counters, decide, and
    only increment *after* the search returned. Between the read and the increment the budget was
    unguarded, so N concurrent cache misses all saw the same under-budget count, all passed, and
    all spent — overshooting the cap by N-1 on a resource that is metered and paid. Redis INCR is
    atomic, so incrementing first and inspecting the returned value means exactly one caller can
    ever see the value that crosses the cap.

    Fail-open on a Redis outage is deliberate and unchanged: ``incr`` returns 0, which reads as
    under budget, so a Redis outage degrades to "unmetered" rather than "product down". That is a
    real trade-off — it means spend is uncapped precisely when we cannot count it — and it is the
    same choice the rate limiter makes. A guard that cannot be released is also not released here:
    a zero from ``incr`` means nothing was claimed, so there is nothing to hand back.
    """
    settings = get_settings()
    day_key, month_key = _budget_keys()

    day_spent = cache.incr(day_key, ttl_seconds=_DAY_TTL_SECONDS)
    month_spent = cache.incr(month_key, ttl_seconds=_MONTH_TTL_SECONDS)

    daily_cap = settings.serpapi_daily_budget
    if daily_cap and day_spent > daily_cap:
        release_search_budget(cache)
        return f"daily search budget reached ({day_spent - 1}/{daily_cap})"

    monthly_cap = settings.serpapi_monthly_budget
    if monthly_cap and month_spent > monthly_cap:
        release_search_budget(cache)
        return f"monthly search budget reached ({month_spent - 1}/{monthly_cap})"

    return ""


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

    # Global budget guard — a cache miss is about to spend real money, so the claim is made
    # atomically BEFORE the search. Concurrent misses can no longer all pass the same check.
    reason = reserve_search_budget(cache)
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
    except Exception:
        # The search never went out, so hand the claim back rather than charging the budget
        # for a request the provider never served.
        release_search_budget(cache)
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

    SEARCH_SPEND.inc()  # a live search actually went out and was served

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
