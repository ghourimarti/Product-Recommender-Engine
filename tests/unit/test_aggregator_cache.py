"""Unit tests for cached aggregation (Aggregator A3). Offline: fakeredis + fake LLM/search."""

from __future__ import annotations

from typing import Any

import fakeredis
from langchain_core.runnables import RunnableLambda

from core.cache import RedisCache
from core.models import ExplanationSet, Offer
from recommender.aggregator import aggregate


class _FakeModel:
    """Minimal chat-model stub: with_structured_output -> a Runnable returning an ExplanationSet."""

    def with_structured_output(self, schema: object) -> Any:
        return RunnableLambda(lambda _inputs: ExplanationSet(summary="s", explanations=[]))


def _offer(product_id: str) -> Offer:
    return Offer(
        product_id=product_id,
        title=product_id,
        price=10.0,
        store="Amazon.com",
        product_url=f"https://buy/{product_id}",
        rating=4.0,
        review_count=100,
        position=1,
    )


def test_aggregate_caches_serpapi_search() -> None:
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    calls = {"n": 0}

    def fake_search(query: str, num: int) -> list[Offer]:
        calls["n"] += 1
        return [_offer("A"), _offer("B")]

    first = aggregate("bass headphones", cache, _FakeModel(), k=2, search_fn=fake_search)
    second = aggregate("bass headphones", cache, _FakeModel(), k=2, search_fn=fake_search)

    assert calls["n"] == 1  # second query served from cache -> NO paid SerpApi call
    assert first.no_match is False
    assert [o.offer.product_id for o in first.offers] == [o.offer.product_id for o in second.offers]


def test_aggregate_source_failure_is_no_match() -> None:
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))

    def boom(query: str, num: int) -> list[Offer]:
        raise RuntimeError("serpapi down")

    result = aggregate("x", cache, _FakeModel(), search_fn=boom)
    assert result.no_match is True
    assert result.offers == []
