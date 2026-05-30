"""Retriever assembly (Decision 6: advanced RAG).

Wraps a vector store into the retriever the chain uses. Reranking is a feature flag:
when on, we over-fetch (``retrieval_fetch_k`` candidates) then a cross-encoder reranker
compresses to ``rerank_top_n``; when off, we retrieve ``retrieval_k`` directly.

Dense + no-rerank is verified against a real Qdrant container. The rerank path uses
FlashRank (ONNX, no torch — cheap to run) and is verified in a 3.12 venv.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


def build_retriever(vectorstore: Any) -> Any:
    if not settings.use_reranker:
        logger.info("retriever_plain", extra={"k": settings.retrieval_k})
        return vectorstore.as_retriever(search_kwargs={"k": settings.retrieval_k})

    from langchain.retrievers import ContextualCompressionRetriever
    from langchain_community.document_compressors import FlashrankRerank

    base = vectorstore.as_retriever(search_kwargs={"k": settings.retrieval_fetch_k})
    compressor = FlashrankRerank(model=settings.reranker_model, top_n=settings.rerank_top_n)
    logger.info(
        "retriever_reranked",
        extra={"fetch_k": settings.retrieval_fetch_k, "top_n": settings.rerank_top_n},
    )
    return ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base)
