"""Unit tests for the aggregator no-match gate. Offline: fakeredis + fake embeddings/search."""

from __future__ import annotations

import math
from typing import Any

import fakeredis
from langchain_core.runnables import RunnableLambda

from core.cache import RedisCache
from core.models import ExplanationSet, Offer
from recommender.aggregator import aggregate, aggregate_stream, offers_relevance


class _FakeEmbeddings:
    """embed_documents([query, *titles]) -> vectors whose cosine to the query is `sim`."""

    def __init__(self, sim: float) -> None:
        self._sim = sim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        title_vec = [self._sim, math.sqrt(max(0.0, 1.0 - self._sim**2))]
        return [[1.0, 0.0], *(title_vec for _ in texts[1:])]


class _FakeModel:
    def with_structured_output(self, schema: object) -> Any:
        return RunnableLambda(lambda _in: ExplanationSet(summary="s", explanations=[]))


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


def _cache() -> RedisCache:
    return RedisCache(fakeredis.FakeRedis(decode_responses=True))


def test_offers_relevance_matches_expected_cosine() -> None:
    rel = offers_relevance("q", [_offer("A")], _FakeEmbeddings(0.4))
    assert abs(rel - 0.4) < 1e-6


def test_gate_rejects_irrelevant_offers() -> None:
    # model is None: if the gate wrongly let this through, explain_offers(None) would crash.
    stages = list(
        aggregate_stream(
            "gibberish",
            _cache(),
            None,
            search_fn=lambda q, n: [_offer("A"), _offer("B")],
            embeddings=_FakeEmbeddings(0.10),  # below the 0.25 floor
        )
    )
    assert stages[-1][0] == "final"
    assert stages[-1][1].no_match is True
    assert stages[-1][1].offers == []


def test_gate_allows_relevant_offers() -> None:
    gen = aggregate_stream(
        "wifi router",
        _cache(),
        _FakeModel(),
        search_fn=lambda q, n: [_offer("A"), _offer("B")],
        embeddings=_FakeEmbeddings(0.50),  # above the floor
    )
    stage, result = next(gen)  # gate passed -> cards emitted first
    assert stage == "offers"
    assert result.no_match is False
    assert len(result.offers) >= 1


def test_gate_skipped_without_embeddings() -> None:
    # Backward-compatible: no embeddings -> no gate -> existing behaviour unchanged.
    result = aggregate("anything", _cache(), _FakeModel(), search_fn=lambda q, n: [_offer("A")])
    assert result.no_match is False
