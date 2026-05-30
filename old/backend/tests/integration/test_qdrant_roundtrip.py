"""Step 4: Qdrant integration round-trip.

Verifies the *plumbing* of QdrantVectorStoreProvider against a real Qdrant container:
collection creation, document upsert, and similarity search round-trip. Retrieval *quality*
(real bge embeddings + RAGAS) is a separate, keyed concern (Steps 5-6).

A deterministic stub embedding is used as a test double so this runs without GPU/keys.
Skips automatically if no Qdrant is reachable at QDRANT_URL.
"""
from __future__ import annotations

import hashlib
import os

import pytest

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_DIM = 32


def _qdrant_up() -> bool:
    try:
        import httpx

        return httpx.get(f"{QDRANT_URL}/readyz", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable at QDRANT_URL")


def _stub_embeddings():
    """Deterministic hash-based embeddings. Subclasses LangChain's Embeddings ABC because
    langchain-qdrant type-checks the instance. Proves the store contract, not quality."""
    from langchain_core.embeddings import Embeddings

    class StubEmbeddings(Embeddings):
        def _vec(self, text: str) -> list[float]:
            digest = hashlib.sha256(text.encode()).digest()
            raw = [digest[i % len(digest)] / 255.0 for i in range(_DIM)]
            norm = sum(x * x for x in raw) ** 0.5 or 1.0
            return [x / norm for x in raw]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self._vec(t) for t in texts]

        def embed_query(self, text: str) -> list[float]:
            return self._vec(text)

    return StubEmbeddings()


def _dense_provider(collection: str):
    from app.core.config import settings
    from app.rag.adapters.qdrant_store import QdrantVectorStoreProvider

    # Force dense mode (hybrid is the default but needs the fastembed sparse model -> 3.12).
    settings.embedding_dim = _DIM
    settings.retrieval_mode = "dense"
    return QdrantVectorStoreProvider(embedding=_stub_embeddings(), collection_name=collection)


def _sample_docs():
    from langchain_core.documents import Document

    return [
        Document(page_content="great noise cancelling headphones", metadata={"product_name": "Headphones X"}),
        Document(page_content="durable running shoes for marathons", metadata={"product_name": "Shoes Y"}),
    ]


def test_qdrant_upsert_and_search():
    provider = _dense_provider("test_roundtrip_collection")
    provider.add_documents(_sample_docs())

    results = provider.get_vectorstore().similarity_search("great noise cancelling headphones", k=1)
    assert len(results) == 1
    assert results[0].metadata["product_name"] == "Headphones X"


def test_build_retriever_dense_no_rerank():
    """Step 6: the engine's retrieval wiring (dense, rerank off) works against real Qdrant."""
    from app.core.config import settings
    from app.rag.retriever import build_retriever

    settings.use_reranker = False
    provider = _dense_provider("test_retriever_collection")
    provider.add_documents(_sample_docs())

    retriever = build_retriever(provider.get_vectorstore())
    docs = retriever.invoke("great noise cancelling headphones")
    assert any(d.metadata["product_name"] == "Headphones X" for d in docs)
