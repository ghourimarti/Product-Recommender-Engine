"""Cached recommendation path: L3 exact -> L1 embed -> L2 semantic -> compute.

Order matters: cheapest/most-specific first. An L2 hit is promoted into L3 so the next
identical query is an exact hit. Only the retrieval+ranking is cached (the /chat explanation
still streams fresh).
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import Counter

from core.cache import (
    CACHE_HITS,
    CACHE_MISSES,
    RedisCache,
    cached_embed_query,
    get_catalog_version,
    hash_key,
    normalize_query,
)
from core.config import get_settings
from core.models import RankingResult
from core.observability import tracer
from recommender.ranking import RankingConfig
from recommender.service import recommend
from retrieval.semantic_cache import SemanticCacheLike
from retrieval.store import VectorStore

logger = logging.getLogger("p2.cached")

# F6: how often we honestly tell the user we have nothing good (alert if this spikes — it can
# also mean retrieval is broken, not that users got fussy).
NO_MATCH = Counter("no_match_total", "Queries the catalog could not answer")

RESPONSE_TTL_SECONDS = 600
SEMANTIC_THRESHOLD = 0.97


def cached_recommend(
    query: str,
    store: VectorStore,
    cache: RedisCache,
    semantic_cache: SemanticCacheLike,
    embeddings: Any,
    *,
    k: int = 5,
    config: RankingConfig | None = None,
) -> RankingResult:
    with tracer.start_as_current_span("recommend.pipeline"):
        settings = get_settings()
        version = get_catalog_version(cache)
        normalized = normalize_query(query)
        response_key = "resp:" + hash_key(version, str(k), normalized)

        # L3 — exact response cache
        cached = cache.get_json(response_key)
        if cached is not None:
            CACHE_HITS.labels("response").inc()
            return RankingResult.model_validate(cached)
        CACHE_MISSES.labels("response").inc()

        # L1 — embedding cache (vector reused by L2 and by the no-match gate)
        query_vector = cached_embed_query(normalized, embeddings, cache, settings.embedding_model)

        # L2 — semantic cache
        semantic_hit = semantic_cache.lookup(query_vector, version, SEMANTIC_THRESHOLD)
        if semantic_hit is not None:
            CACHE_HITS.labels("semantic").inc()
            cache.set_json(response_key, semantic_hit.model_dump(), RESPONSE_TTL_SECONDS)  # promote
            return semantic_hit
        CACHE_MISSES.labels("semantic").inc()

        # F6 "no good match" gate. Hybrid/RRF scores are relative — the top hit is ~1.0 even for
        # a query this catalog cannot answer (asking for a refrigerator returned headphones).
        # Gate on the ABSOLUTE dense cosine instead, so an off-topic query is honestly rejected.
        similarity = store.max_dense_similarity(query_vector)
        if similarity < settings.min_semantic_similarity:
            logger.info(
                "no_match: similarity %.3f below floor %.2f",
                similarity,
                settings.min_semantic_similarity,
            )
            NO_MATCH.inc()
            empty = RankingResult(products=[], no_match=True)
            cache.set_json(response_key, empty.model_dump(), RESPONSE_TTL_SECONDS)
            return empty

        # Miss — compute, then populate L3 + L2
        result = recommend(normalized, store, k=k, config=config)
        cache.set_json(response_key, result.model_dump(), RESPONSE_TTL_SECONDS)
        semantic_cache.store(query_vector, version, normalized, result)
        return result
