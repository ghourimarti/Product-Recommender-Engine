"""Embedding factories (Decision 5: OpenAI text-embedding-3-small @1536 dense + BM25 sparse)."""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse
from pydantic import SecretStr

from core.config import get_settings


def get_dense_embeddings() -> OpenAIEmbeddings:
    """Dense embeddings via OpenAI (1536-d), key injected from settings."""
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=SecretStr(settings.openai_api_key),
        dimensions=settings.embedding_dim,
    )


def get_sparse_embeddings() -> FastEmbedSparse:
    """Sparse (BM25) embeddings for the keyword half of hybrid retrieval (runs locally)."""
    return FastEmbedSparse(model_name="Qdrant/bm25")
