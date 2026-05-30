"""End-to-end chat orchestration: rewrite -> retrieve+rank -> grounded explain -> merge.

Lives in recommender (depends on core + retrieval) to avoid a core<->recommender cycle.
The LLM only authors reasons; product facts come from our ranking, merged here.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

from core.llm import build_chat_model, explain, rewrite_query
from core.models import ChatResponse, ExplanationSet, RankedProduct, RecommendationItem
from recommender.ranking import RankingConfig
from recommender.service import recommend
from retrieval.rerank import Reranker
from retrieval.store import VectorStore


def _merge(products: list[RankedProduct], explanations: ExplanationSet) -> ChatResponse:
    reason_by_id = {e.product_id: e.reason for e in explanations.explanations}
    items = [
        RecommendationItem(
            product_id=p.product_id,
            title=p.title,
            avg_rating=p.avg_rating,
            final_score=p.final_score,
            reason=reason_by_id.get(p.product_id, ""),
        )
        for p in products
    ]
    return ChatResponse(summary=explanations.summary, items=items, no_match=False)


def chat(
    query: str,
    history: list[BaseMessage],
    store: VectorStore,
    *,
    k: int = 5,
    config: RankingConfig | None = None,
    reranker: Reranker | None = None,
    model: Any = None,
) -> ChatResponse:
    """Answer a shopper query with grounded, ranked recommendations."""
    chat_model = model if model is not None else build_chat_model()
    standalone = rewrite_query(query, history, chat_model) if history else query
    result = recommend(standalone, store, k=k, config=config, reranker=reranker)
    if result.no_match or not result.products:
        return ChatResponse(
            summary="Sorry, I couldn't find a good match for that.", items=[], no_match=True
        )
    explanations = explain(standalone, result.products, chat_model)
    return _merge(result.products, explanations)
