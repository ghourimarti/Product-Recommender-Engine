"""Qdrant hybrid (dense + sparse) vector store behind a swappable interface (Decision 2).

The ``VectorStore`` Protocol is the seam that keeps Decision 2 reversible: swapping
Qdrant for pgvector/Pinecone later means writing one new implementation, not touching
callers. All langchain-qdrant calls are confined here so the rest of the codebase stays
strictly typed.
"""

from __future__ import annotations

from typing import Any, Protocol

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, RetrievalMode

from core.config import get_settings
from core.embeddings import get_dense_embeddings, get_sparse_embeddings
from core.models import Product, RetrievedProduct


class VectorStore(Protocol):
    """The retrieval contract callers depend on (not the concrete Qdrant impl)."""

    def index(self, products: list[Product]) -> None: ...

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]: ...


def _product_to_document(product: Product) -> Document:
    return Document(
        page_content=product.combined_text,
        metadata={
            "product_id": product.product_id,
            "title": product.title,
            "avg_rating": product.avg_rating,
            "review_count": product.review_count,
        },
    )


def _to_retrieved(doc: Document, score: float) -> RetrievedProduct:
    meta = doc.metadata
    return RetrievedProduct(
        product_id=str(meta["product_id"]),
        title=str(meta["title"]),
        avg_rating=float(meta["avg_rating"]),
        review_count=int(meta["review_count"]),
        semantic_score=float(score),
        text=doc.page_content,
    )


class QdrantHybridStore:
    """Hybrid dense+sparse store backed by Qdrant via langchain-qdrant."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._dense = get_dense_embeddings()
        self._sparse = get_sparse_embeddings()
        self._store: Any = None

    def index(self, products: list[Product]) -> None:
        documents = [_product_to_document(p) for p in products]
        self._store = QdrantVectorStore.from_documents(
            documents=documents,
            embedding=self._dense,
            sparse_embedding=self._sparse,
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key or None,
            collection_name=self._settings.qdrant_collection,
            retrieval_mode=RetrievalMode.HYBRID,
            force_recreate=True,
        )

    def _ensure_store(self) -> Any:
        if self._store is None:
            self._store = QdrantVectorStore.from_existing_collection(
                embedding=self._dense,
                sparse_embedding=self._sparse,
                url=self._settings.qdrant_url,
                api_key=self._settings.qdrant_api_key or None,
                collection_name=self._settings.qdrant_collection,
                retrieval_mode=RetrievalMode.HYBRID,
            )
        return self._store

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]:
        store = self._ensure_store()
        hits = store.similarity_search_with_score(query, k=k)
        return [_to_retrieved(doc, score) for doc, score in hits]
