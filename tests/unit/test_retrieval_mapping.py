"""Unit test for the Document -> RetrievedProduct mapping (no external services)."""

from __future__ import annotations

from langchain_core.documents import Document

from retrieval.store import _to_retrieved


def test_to_retrieved_maps_metadata_and_score() -> None:
    doc = Document(
        page_content="great bass and battery",
        metadata={"product_id": "A", "title": "BoAt Buds", "avg_rating": 4.4, "review_count": 50},
    )
    result = _to_retrieved(doc, 0.87)
    assert result.product_id == "A"
    assert result.title == "BoAt Buds"
    assert result.avg_rating == 4.4
    assert result.review_count == 50
    assert result.semantic_score == 0.87
    assert result.text == "great bass and battery"
