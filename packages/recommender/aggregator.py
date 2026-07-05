"""Aggregator orchestration: rank live offers, then attach grounded LLM reasons.

Search (the live SerpApi call) is injected by the caller (API, Step A3) so this stays
testable offline and search-free.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from core.cache import CACHE_HITS, CACHE_MISSES, RedisCache, hash_key, normalize_query
from core.llm import explain_offers
from core.models import AggregatorResult, ExplanationSet, Offer, RankedOffer
from recommender.offer_ranking import rank_offers
from recommender.ranking import RankingConfig
from sources.serpapi_source import search_offers

logger = logging.getLogger("p2.aggregator")

# Cache the whole result (offers + reasons) so a repeat query costs 0 SerpApi searches AND
# 0 LLM calls within the window. This is the key cost control for the metered SerpApi quota.
AGGREGATE_TTL_SECONDS = 600


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
    """Cached live aggregation: cache-hit -> 0 SerpApi/LLM; miss -> 1 search + rank + explain.

    ``search_fn`` (the live SerpApi call) is injected so tests run offline and search-free.
    """
    search = search_fn if search_fn is not None else (lambda q, n: search_offers(q, num=n))
    key = "agg:" + hash_key(str(k), normalize_query(query))

    cached = cache.get_json(key)
    if cached is not None:
        CACHE_HITS.labels("aggregate").inc()
        return AggregatorResult.model_validate(cached)
    CACHE_MISSES.labels("aggregate").inc()

    try:
        offers = search(query, num)
    except Exception:  # shopping source down -> graceful no-match (Decision 21)
        logger.warning("shopping source failed; returning no-match", exc_info=True)
        return AggregatorResult(query=query, offers=[], no_match=True)

    result = rank_and_explain(query, offers, model, k=k, config=config, callbacks=callbacks)
    cache.set_json(key, result.model_dump(), AGGREGATE_TTL_SECONDS)
    return result
