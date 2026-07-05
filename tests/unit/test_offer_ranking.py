"""Unit tests for offer ranking + reason merge (Aggregator A2). Offline, no LLM/search."""

from __future__ import annotations

from core.models import Explanation, ExplanationSet, Offer
from recommender.aggregator import merge_offer_reasons
from recommender.offer_ranking import rank_offers


def _offer(
    product_id: str, position: int, rating: float | None, reviews: int = 1000, price: float = 100.0
) -> Offer:
    return Offer(
        product_id=product_id,
        title=product_id,
        price=price,
        store="Amazon.com",
        product_url=f"https://buy/{product_id}",
        rating=rating,
        review_count=reviews,
        position=position,
    )


def test_empty_offers() -> None:
    assert rank_offers([]) == []


def test_position_relevance_dominates() -> None:
    # Same rating; the higher-positioned (Google-ranked) offer should win on relevance.
    ranked = rank_offers([_offer("second", 2, 4.5), _offer("first", 1, 4.5)])
    assert ranked[0].offer.product_id == "first"


def test_rating_breaks_tie_at_same_position() -> None:
    ranked = rank_offers([_offer("low", 1, 3.0), _offer("high", 1, 5.0)])
    assert ranked[0].offer.product_id == "high"


def test_missing_rating_is_neutral_not_zero() -> None:
    # An unrated but top-positioned offer should still rank above a poorly rated one.
    ranked = rank_offers([_offer("unrated", 1, None), _offer("bad", 2, 1.0)])
    assert ranked[0].offer.product_id == "unrated"


def test_scores_in_unit_interval() -> None:
    ranked = rank_offers([_offer("A", 1, 5.0, reviews=100000)])
    r = ranked[0]
    assert 0.0 <= r.final_score <= 1.0
    assert 0.0 <= r.relevance_score <= 1.0
    assert 0.0 <= r.rating_score <= 1.0
    assert 0.0 <= r.volume_confidence <= 1.0


def test_merge_offer_reasons() -> None:
    ranked = rank_offers([_offer("A", 1, 4.0), _offer("B", 2, 4.0)])
    explanations = ExplanationSet(
        summary="two picks",
        explanations=[Explanation(product_id="A", reason="great value")],
    )
    merged = merge_offer_reasons(ranked, explanations)
    by_id = {m.offer.product_id: m.reason for m in merged}
    assert by_id["A"] == "great value"
    assert by_id["B"] == ""  # no reason returned -> empty, not an error
