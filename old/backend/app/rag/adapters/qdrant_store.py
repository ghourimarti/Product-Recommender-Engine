"""Qdrant vector-store provider (Decision 2 — locked target backend).

Returns a LangChain ``QdrantVectorStore`` so the existing chain works unchanged. Supports
dense and hybrid (dense + BM25 sparse) retrieval modes (Decision 6). The embedding is
injectable so the upsert/search round-trip is verifiable against a real Qdrant container
without GPU/keys (dense path). The hybrid path follows the langchain-qdrant API and is
verified in a Python 3.12 venv (needs the fastembed sparse model).
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


class QdrantVectorStoreProvider:
    def __init__(self, embedding: Any | None = None, collection_name: str | None = None) -> None:
        self._embedding = embedding
        self._collection = collection_name or settings.vector_collection_name
        self._store: Any = None

    def _get_embedding(self) -> Any:
        if self._embedding is None:
            if settings.embedding_provider == "service":
                from app.rag.adapters.http_embeddings import HTTPEmbeddings

                self._embedding = HTTPEmbeddings()
            else:
                from langchain_huggingface import HuggingFaceEndpointEmbeddings

                self._embedding = HuggingFaceEndpointEmbeddings(model=settings.embedding_model)
        return self._embedding

    def _client(self) -> Any:
        from qdrant_client import QdrantClient

        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    def _build_dense(self, client: Any) -> Any:
        from langchain_qdrant import QdrantVectorStore, RetrievalMode
        from qdrant_client.models import Distance, VectorParams

        if not client.collection_exists(self._collection):
            client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
            )
            logger.info("qdrant_dense_collection_created", extra={"collection": self._collection})
        return QdrantVectorStore(
            client=client,
            collection_name=self._collection,
            embedding=self._get_embedding(),
            retrieval_mode=RetrievalMode.DENSE,
        )

    def _build_hybrid(self, client: Any) -> Any:
        # Verified in a 3.12 venv (needs the fastembed sparse model download).
        from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
        from qdrant_client.models import Distance, SparseVectorParams, VectorParams

        sparse = FastEmbedSparse(model_name=settings.sparse_model)
        if not client.collection_exists(self._collection):
            client.create_collection(
                collection_name=self._collection,
                vectors_config={"dense": VectorParams(size=settings.embedding_dim, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": SparseVectorParams()},
            )
            logger.info("qdrant_hybrid_collection_created", extra={"collection": self._collection})
        return QdrantVectorStore(
            client=client,
            collection_name=self._collection,
            embedding=self._get_embedding(),
            sparse_embedding=sparse,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )

    def get_vectorstore(self) -> Any:
        if self._store is None:
            client = self._client()
            if settings.retrieval_mode == "hybrid":
                self._store = self._build_hybrid(client)
            else:
                self._store = self._build_dense(client)
            logger.info("qdrant_store_initialized", extra={"mode": settings.retrieval_mode})
        return self._store

    def add_documents(self, docs: list[Any]) -> None:
        self.get_vectorstore().add_documents(docs)
        logger.info("qdrant_documents_added", extra={"count": len(docs)})
