"""Unit test for the recommend() orchestration using a fake store (no services)."""

from __future__ import annotations

from core.models import Product, RetrievedProduct
from recommender.service import recommend


class FakeStore:
    """In-memory VectorStore stand-in for testing recommend() without Qdrant."""

    def __init__(self, results: list[RetrievedProduct]) -> None:
        self._results = results

    def index(self, products: list[Product]) -> None:
        return None

    def max_dense_similarity(self, query_vector: list[float]) -> float:
        return 0.9  # on-topic; the no-match gate is exercised in test_cache.py

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]:
        return self._results[:k]


def _rp(product_id: str, semantic: float, rating: float = 4.5) -> RetrievedProduct:
    return RetrievedProduct(
        product_id=product_id,
        title=product_id,
        avg_rating=rating,
        review_count=50,
        semantic_score=semantic,
        text="...",
    )


def test_recommend_retrieves_then_ranks() -> None:
    store = FakeStore([_rp("A", semantic=0.3, rating=5.0), _rp("B", semantic=0.95, rating=4.0)])
    result = recommend("any query", store, k=5)
    assert [p.product_id for p in result.products] == ["B", "A"]  # relevance dominates
    assert result.no_match is False


def test_recommend_respects_k() -> None:
    store = FakeStore([_rp("A", 0.9), _rp("B", 0.8), _rp("C", 0.7)])
    result = recommend("q", store, k=2)
    assert len(result.products) == 2
