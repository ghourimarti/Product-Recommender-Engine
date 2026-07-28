"""Unit tests for ranking metrics. Pure, no services."""

from __future__ import annotations

from evaluation.ranking.metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_perfect() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, 3) == 1.0


def test_recall_partial_when_relevant_exceeds_k() -> None:
    # 5 relevant, only 3 can appear in top-3 -> max 0.6
    assert recall_at_k(["a", "b", "c", "x", "y"], {"a", "b", "c", "d", "e"}, 3) == 0.6


def test_recall_zero_when_none_found() -> None:
    assert recall_at_k(["x", "y"], {"a"}, 2) == 0.0


def test_precision_at_k() -> None:
    assert precision_at_k(["a", "x", "b"], {"a", "b"}, 3) == 2 / 3


def test_ndcg_perfect_is_one() -> None:
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 2) == 1.0


def test_ndcg_is_order_sensitive() -> None:
    first = ndcg_at_k(["a", "x"], {"a"}, 2)  # relevant at rank 1
    later = ndcg_at_k(["x", "a"], {"a"}, 2)  # relevant at rank 2
    assert first == 1.0
    assert later < first


def test_mrr_uses_first_relevant_rank() -> None:
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3


def test_mrr_zero_when_absent() -> None:
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0
