"""Unit tests for chat merge + provider selection (Step 6). Pure, no LLM/services."""

from __future__ import annotations

from core.config import Settings
from core.llm import available_providers
from core.models import Explanation, ExplanationSet, RankedProduct
from recommender.chat import _merge


def _ranked(product_id: str, title: str = "T", final: float = 0.9) -> RankedProduct:
    return RankedProduct(
        product_id=product_id,
        title=title,
        final_score=final,
        relevance_score=0.9,
        rating_score=0.8,
        volume_confidence=1.0,
        avg_rating=4.5,
        review_count=50,
        semantic_score=0.9,
        text="great product",
    )


def test_merge_joins_reasons_by_product_id() -> None:
    products = [_ranked("A", "Prod A"), _ranked("B", "Prod B")]
    explanations = ExplanationSet(
        summary="two good picks",
        explanations=[
            Explanation(product_id="A", reason="reason a"),
            Explanation(product_id="B", reason="reason b"),
        ],
    )
    resp = _merge(products, explanations)
    assert resp.summary == "two good picks"
    assert resp.no_match is False
    assert [i.product_id for i in resp.items] == ["A", "B"]
    assert resp.items[0].reason == "reason a"


def test_merge_missing_reason_becomes_empty() -> None:
    resp = _merge([_ranked("A")], ExplanationSet(summary="s", explanations=[]))
    assert resp.items[0].reason == ""


def test_available_providers_priority_order() -> None:
    settings = Settings(groq_api_key="g", openai_api_key="o", anthropic_api_key="a")
    assert available_providers(settings) == ["groq", "openai", "anthropic"]


def test_available_providers_openai_only() -> None:
    settings = Settings(groq_api_key="", openai_api_key="o", anthropic_api_key="")
    assert available_providers(settings) == ["openai"]


def test_available_providers_none() -> None:
    settings = Settings(groq_api_key="", openai_api_key="", anthropic_api_key="")
    assert available_providers(settings) == []
