"""Recommendation orchestration: retrieve (Qdrant hybrid) -> rank (rating-aware blend).

Depends only on the ``VectorStore`` protocol, so it is unit-testable with a fake store
and reusable from the API and the LangChain chain.
"""

from __future__ import annotations

from core.models import RankingResult
from recommender.ranking import RankingConfig, rank_products
from retrieval.rerank import Reranker
from retrieval.store import VectorStore


def recommend(
    query: str,
    store: VectorStore,
    k: int = 5,
    config: RankingConfig | None = None,
    reranker: Reranker | None = None,
) -> RankingResult:
    """Retrieve ``k`` candidates, optionally rerank, then rating-aware rank them."""
    candidates = store.search(query, k=k)
    if reranker is not None:
        candidates = reranker.rerank(query, candidates)
    return rank_products(candidates, config)
