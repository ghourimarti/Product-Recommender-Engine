"""Wiring: select the vector backend + assemble the AnswerEngine.

This is the single place backend selection happens. Step 4 adds a ``qdrant`` branch here;
nothing else in the app needs to change.
"""
from __future__ import annotations

from app.core.config import settings
from app.rag.engine import LangChainAnswerEngine
from app.rag.interfaces import AnswerEngine, VectorStoreProvider


def build_vector_store_provider() -> VectorStoreProvider:
    backend = settings.vector_backend.lower()
    if backend == "qdrant":
        from app.rag.adapters.qdrant_store import QdrantVectorStoreProvider

        return QdrantVectorStoreProvider()
    if backend == "astra":
        from app.rag.adapters.astra_store import AstraVectorStoreProvider

        return AstraVectorStoreProvider()
    raise ValueError(f"Unknown vector_backend: {settings.vector_backend!r}")


def build_answer_engine() -> AnswerEngine:
    provider = build_vector_store_provider()
    engine = LangChainAnswerEngine(provider)
    engine.build()
    return engine


def build_chat_cache():
    """Build the ChatCache, or return None if caching is disabled (Decision 10)."""
    if not settings.cache_enabled:
        return None
    from app.cache.chat_cache import ChatCache
    from app.cache.redis_cache import get_redis

    embedder = build_vector_store_provider()._get_embedding() if settings.semantic_cache_enabled else None
    return ChatCache(get_redis(), embedder=embedder)
