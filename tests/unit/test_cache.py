"""Unit tests for caching (Step 9) using fakeredis. No external services."""

from __future__ import annotations

from typing import Any

import fakeredis
import pytest

from core.cache import (
    RedisCache,
    bump_catalog_version,
    cached_embed_query,
    clear_version_memo,
    get_catalog_version,
    hash_key,
    normalize_query,
)
from core.models import RankingResult, RetrievedProduct
from recommender.cached import cached_recommend


@pytest.fixture
def cache() -> RedisCache:
    clear_version_memo()
    return RedisCache(fakeredis.FakeRedis(decode_responses=True))


def test_normalize_query() -> None:
    assert normalize_query("  Best   BASS headphones ") == "best bass headphones"


def test_hash_key_is_deterministic_and_order_sensitive() -> None:
    assert hash_key("a", "b") == hash_key("a", "b")
    assert hash_key("a", "b") != hash_key("b", "a")


def test_redis_json_roundtrip(cache: RedisCache) -> None:
    cache.set_json("k", {"x": 1}, 60)
    assert cache.get_json("k") == {"x": 1}
    assert cache.get_json("missing") is None


def test_catalog_version_bump_changes_value(cache: RedisCache) -> None:
    first = get_catalog_version(cache)
    bumped = bump_catalog_version(cache)
    assert bumped != first


class _FakeEmbeddings:
    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return [0.1] * 8


def test_cached_embed_query_uses_cache(cache: RedisCache) -> None:
    embeddings = _FakeEmbeddings()
    first = cached_embed_query("q", embeddings, cache, "model")
    second = cached_embed_query("q", embeddings, cache, "model")
    assert first == second
    assert embeddings.calls == 1  # second call served from L1


class _FakeStore:
    def __init__(self) -> None:
        self.search_calls = 0

    def index(self, products: list[Any]) -> None:
        return None

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]:
        self.search_calls += 1
        return [
            RetrievedProduct(
                product_id="A",
                title="A",
                avg_rating=4.5,
                review_count=50,
                semantic_score=0.9,
                text="great bass",
            )
        ]


class _NoSemanticCache:
    def lookup(
        self, query_vector: list[float], version: str, threshold: float = 0.97
    ) -> RankingResult | None:
        return None

    def store(
        self, query_vector: list[float], version: str, query: str, result: RankingResult
    ) -> None:
        return None


def test_cached_recommend_l3_hit_and_invalidation(cache: RedisCache) -> None:
    store, semantic, embeddings = _FakeStore(), _NoSemanticCache(), _FakeEmbeddings()

    first = cached_recommend("good bass", store, cache, semantic, embeddings, k=3)
    second = cached_recommend("good bass", store, cache, semantic, embeddings, k=3)
    assert store.search_calls == 1  # second served from L3 response cache
    assert first.products[0].product_id == second.products[0].product_id == "A"

    bump_catalog_version(cache)  # invalidate
    cached_recommend("good bass", store, cache, semantic, embeddings, k=3)
    assert store.search_calls == 2  # version bump forced a recompute
