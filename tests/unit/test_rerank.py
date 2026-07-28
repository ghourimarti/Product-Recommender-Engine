"""Unit tests for the reranker scoring/sort logic. Pure, no model download."""

from __future__ import annotations

import pytest

from core.models import RetrievedProduct
from retrieval.rerank import _apply_scores, _sigmoid


def _rp(product_id: str) -> RetrievedProduct:
    return RetrievedProduct(
        product_id=product_id,
        title=product_id,
        avg_rating=4.5,
        review_count=50,
        semantic_score=0.5,
        text=f"text for {product_id}",
    )


def test_sigmoid_bounded_and_monotonic() -> None:
    assert _sigmoid(0.0) == 0.5
    assert 0.0 < _sigmoid(-10.0) < _sigmoid(10.0) < 1.0


def test_apply_scores_sorts_by_reranked_relevance() -> None:
    out = _apply_scores([_rp("A"), _rp("B")], [0.0, 5.0])  # B has the higher logit
    assert out[0].product_id == "B"
    assert out[0].semantic_score > out[1].semantic_score
    assert all(0.0 <= c.semantic_score <= 1.0 for c in out)


def test_apply_scores_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):  # strict zip
        _apply_scores([_rp("A")], [0.1, 0.2])
