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


def test_source_failure_is_reported_as_outage_not_no_match() -> None:
    """A dead SerpApi must NOT masquerade as 'we found nothing'.

    Previously any source failure returned no_match=True, so quota exhaustion / a bad key /
    a network outage looked identical to a legitimate empty result — you could not tell the
    product was broken. They are now distinct, alertable states.
    """
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))

    def boom(query: str, num: int) -> list[Offer]:
        raise RuntimeError("serpapi down")

    result = aggregate("x", cache, _FakeModel(), search_fn=boom)
    assert result.source_unavailable is True
    assert result.no_match is False  # <- the bug: this used to be True
    assert result.offers == []
    assert "unavailable" in result.detail.lower()


def test_no_match_still_means_no_match() -> None:
    """A successful search that returns nothing is a genuine no_match (not an outage)."""
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    result = aggregate("x", cache, _FakeModel(), search_fn=lambda q, n: [])
    assert result.no_match is True
    assert result.source_unavailable is False


def test_global_budget_guard_blocks_spend(monkeypatch: Any) -> None:
    """One user must not be able to drain the whole metered SerpApi quota."""
    from core.config import Settings
    from recommender import aggregator

    monkeypatch.setattr(
        aggregator,
        "get_settings",
        lambda: Settings(serpapi_daily_budget=2, serpapi_monthly_budget=250),
    )
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    calls = {"n": 0}

    def counting_search(query: str, num: int) -> list[Offer]:
        calls["n"] += 1
        return [_offer("A")]

    # Distinct queries each cost a live search; the 3rd must be refused by the budget guard.
    aggregate("q1", cache, _FakeModel(), search_fn=counting_search)
    aggregate("q2", cache, _FakeModel(), search_fn=counting_search)
    third = aggregate("q3", cache, _FakeModel(), search_fn=counting_search)

    assert calls["n"] == 2  # the 3rd search was never spent
    assert third.source_unavailable is True
    assert third.no_match is False
    assert "budget" in third.detail.lower()
