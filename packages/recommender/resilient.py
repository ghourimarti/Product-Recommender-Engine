"""Resilient recommendation: cached path with a circuit breaker -> popularity fallback (D21)."""

from __future__ import annotations

import logging
from typing import Any

from core.cache import RedisCache
from core.models import Product, RankingResult
from core.resilience import CircuitBreaker
from recommender.cached import cached_recommend
from recommender.fallback import popularity_ranking
from recommender.ranking import RankingConfig
from retrieval.semantic_cache import SemanticCacheLike
from retrieval.store import VectorStore

logger = logging.getLogger("p2.resilient")
_default_breaker = CircuitBreaker()


def resilient_recommend(
    query: str,
    store: VectorStore,
    cache: RedisCache,
    semantic_cache: SemanticCacheLike,
    embeddings: Any,
    catalog: list[Product],
    *,
    k: int = 5,
    config: RankingConfig | None = None,
    breaker: CircuitBreaker | None = None,
) -> RankingResult:
    breaker = breaker or _default_breaker

    if breaker.is_open():  # retrieval circuit open -> skip straight to popularity
        logger.warning("retrieval circuit open; serving popularity ranking")
        return popularity_ranking(catalog, k, config)

    try:
        result = cached_recommend(
            query, store, cache, semantic_cache, embeddings, k=k, config=config
        )
        breaker.record_success()
        return result
    except Exception:  # Qdrant/embeddings down -> degrade, never error the user
        logger.warning("retrieval path failed; serving popularity ranking", exc_info=True)
        breaker.record_failure()
        return popularity_ranking(catalog, k, config)
