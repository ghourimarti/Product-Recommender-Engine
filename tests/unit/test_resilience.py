"""Chaos unit tests for failure-mode degradation (Step 13). No external services."""

from __future__ import annotations

import time

import fakeredis

from core.cache import RedisCache, clear_version_memo
from core.models import Product, RetrievedProduct
from core.resilience import CircuitBreaker
from recommender.fallback import popularity_ranking
from recommender.resilient import resilient_recommend


def _product(product_id: str, rating: float, reviews: int = 50) -> Product:
    return Product(
        product_id=product_id,
        title=product_id,
        review_count=reviews,
        avg_rating=rating,
        rating_histogram={1: 0, 2: 0, 3: 0, 4: 0, 5: reviews},
        representative_reviews=["good"],
        summary_phrases=["good"],
        combined_text=f"{product_id} good",
    )


def _cache() -> RedisCache:
    clear_version_memo()
    return RedisCache(fakeredis.FakeRedis(decode_responses=True))


class _FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 8


class _NoSemanticCache:
    def lookup(self, query_vector: list[float], version: str, threshold: float = 0.97) -> None:
        return None

    def store(self, query_vector: list[float], version: str, query: str, result: object) -> None:
        return None


class _BrokenStore:
    def index(self, products: list[Product]) -> None:
        return None

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]:
        raise RuntimeError("qdrant down")


# --- circuit breaker -------------------------------------------------------------------


def test_circuit_breaker_opens_then_half_opens() -> None:
    breaker = CircuitBreaker(fail_max=2, reset_timeout=0.05)
    assert not breaker.is_open()
    breaker.record_failure()
    assert not breaker.is_open()
    breaker.record_failure()
    assert breaker.is_open()
    time.sleep(0.06)
    assert not breaker.is_open()  # half-open after timeout
    breaker.record_success()
    assert not breaker.is_open()


# --- popularity fallback ---------------------------------------------------------------


def test_popularity_ranking_orders_by_rating_and_volume() -> None:
    result = popularity_ranking([_product("low", 3.0), _product("high", 5.0)], k=2)
    assert result.products[0].product_id == "high"
    assert result.products[0].relevance_score == 0.0  # no semantic relevance


# --- resilient_recommend ---------------------------------------------------------------


def test_falls_back_to_popularity_when_store_down() -> None:
    catalog = [_product("A", 5.0), _product("B", 4.0)]
    breaker = CircuitBreaker(fail_max=1)
    result = resilient_recommend(
        "q",
        _BrokenStore(),
        _cache(),
        _NoSemanticCache(),
        _FakeEmbeddings(),
        catalog,
        k=2,
        breaker=breaker,
    )
    assert [p.product_id for p in result.products] == ["A", "B"]  # popularity order
    assert breaker.is_open()  # failure recorded


def test_open_circuit_skips_straight_to_popularity() -> None:
    breaker = CircuitBreaker(fail_max=1)
    breaker.record_failure()  # open it
    assert breaker.is_open()
    result = resilient_recommend(
        "q",
        _BrokenStore(),
        _cache(),
        _NoSemanticCache(),
        _FakeEmbeddings(),
        [_product("X", 5.0)],
        k=1,
        breaker=breaker,
    )
    assert result.products[0].product_id == "X"


# --- resilient cache (Redis down) ------------------------------------------------------


class _BrokenRedis:
    def get(self, key: str) -> str:
        raise ConnectionError("redis down")

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise ConnectionError("redis down")

    def incr(self, key: str) -> int:
        raise ConnectionError("redis down")

    def expire(self, key: str, ttl: int) -> None:
        raise ConnectionError("redis down")


def test_cache_degrades_on_redis_failure() -> None:
    cache = RedisCache(_BrokenRedis())
    assert cache.get_json("k") is None  # read -> miss
    cache.set_json("k", {"x": 1}, 60)  # write -> no raise
    assert cache.incr_window("rl", 60) == 0  # rate-limit counter fails open
