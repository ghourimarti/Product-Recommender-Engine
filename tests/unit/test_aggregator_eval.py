"""Unit tests for the aggregator eval + gate. Offline: recorded fixtures, 0 SerpApi cost."""

from __future__ import annotations

from core.models import Offer
from evaluation.aggregator.gate import evaluate_gate
from evaluation.aggregator.run import aggregate_metrics, evaluate, is_good, load_fixtures


def _offer(pid: str, rating: float | None, reviews: int, position: int) -> Offer:
    return Offer(
        product_id=pid,
        title=pid,
        price=10.0,
        store="s",
        product_url="u",
        rating=rating,
        review_count=reviews,
        position=position,
    )


def test_good_offer_requires_rating_and_volume() -> None:
    # The whole point of the volume-confidence term: a thin 5-star is NOT a good pick.
    assert is_good(_offer("solid", 4.7, 6200, 1))
    assert not is_good(_offer("thin-5-star", 5.0, 3, 1))  # great rating, no corroboration
    assert not is_good(_offer("well-reviewed-but-bad", 3.6, 5000, 1))
    assert not is_good(_offer("unrated", None, 0, 1))


def test_fixtures_are_present_and_parse() -> None:
    fixtures = load_fixtures()
    assert len(fixtures) >= 3  # multi-category, recorded from real Google Shopping
    assert all(len(offers) > 0 for offers in fixtures.values())


def test_our_ranking_beats_google_order() -> None:
    """The product's core claim, asserted in CI: we re-rank Google's results for the better."""
    metrics = aggregate_metrics(evaluate())
    assert metrics["ndcg_at_3"] > metrics["google_ndcg_at_3"]
    assert metrics["mrr"] >= metrics["google_mrr"]


def test_gate_fails_on_regression() -> None:
    baseline = {"ndcg_at_3": 0.94, "mrr": 1.0, "tolerance": 0.05, "must_beat_google": False}
    regressed = {"ndcg_at_3": 0.50, "mrr": 0.50, "google_ndcg_at_3": 0.8, "google_mrr": 0.8}
    ok, reasons = evaluate_gate(regressed, baseline, 0.05)
    assert ok is False
    assert any("REGRESSION" in r for r in reasons)


def test_gate_fails_when_we_stop_beating_google() -> None:
    baseline = {"ndcg_at_3": 0.94, "mrr": 1.0, "tolerance": 0.05, "must_beat_google": True}
    # Within tolerance of the baseline, but no better than Google -> must still FAIL.
    metrics = {
        "ndcg_at_3": 0.92,
        "mrr": 0.98,
        "google_ndcg_at_3": 0.95,
        "google_mrr": 0.99,
    }
    ok, reasons = evaluate_gate(metrics, baseline, 0.05)
    assert ok is False
    assert any("beats_google" in r for r in reasons)
