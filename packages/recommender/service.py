"""Recommendation orchestration: retrieve (Qdrant hybrid) -> rank (rating-aware blend).

Depends only on the ``VectorStore`` protocol, so it is unit-testable with a fake store
and reusable from the API (Step 8) and the LangChain chain (Step 6).
"""

from __future__ import annotations

from core.models import RankingResult
from recommender.ranking import RankingConfig, rank_products
from retrieval.store import VectorStore


def recommend(
    query: str,
    store: VectorStore,
    k: int = 5,
    config: RankingConfig | None = None,
) -> RankingResult:
    """Retrieve ``k`` candidates for ``query`` and return rating-aware ranked recommendations."""
    candidates = store.search(query, k=k)
    return rank_products(candidates, config)
