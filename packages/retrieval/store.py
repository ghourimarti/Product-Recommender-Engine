"""Qdrant hybrid (dense + sparse) vector store behind a swappable interface.

The ``VectorStore`` Protocol keeps the backend swappable: swapping
Qdrant for pgvector/Pinecone later means writing one new implementation, not touching
callers. All langchain-qdrant calls are confined here so the rest of the codebase stays
strictly typed.
"""

from __future__ import annotations

from typing import Any, Protocol

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from core.config import get_settings
from core.embeddings import get_dense_embeddings, get_sparse_embeddings
from core.models import Product, RetrievedProduct


class VectorStore(Protocol):
    """The retrieval contract callers depend on (not the concrete Qdrant impl)."""

    def index(self, products: list[Product]) -> None: ...

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]: ...

    def max_dense_similarity(self, query_vector: list[float]) -> float: ...


def _product_to_document(product: Product, catalog: str = "") -> Document:
    metadata: dict[str, Any] = {
        "product_id": product.product_id,
        "title": product.title,
        "avg_rating": product.avg_rating,
        "review_count": product.review_count,
    }
    if catalog:
        metadata["catalog"] = catalog  # fingerprint of the catalog file this point came from
    return Document(page_content=product.combined_text, metadata=metadata)


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
        self._client: Any = None

    def _qdrant(self) -> Any:
        if self._client is None:
            self._client = QdrantClient(
                url=self._settings.qdrant_url, api_key=self._settings.qdrant_api_key or None
            )
        return self._client

    def holds_catalog(self, catalog: str, size: int) -> bool:
        """True when the collection holds exactly `size` points, all stamped with `catalog`.

        Lets the seed Job run on every deploy without rebuilding an up-to-date collection
        (Argo CD runs Helm post-install hooks on every sync, and `index` recreates the collection).
        """
        client = self._qdrant()
        if not client.collection_exists(self._settings.qdrant_collection):
            return False
        points, _ = client.scroll(
            collection_name=self._settings.qdrant_collection,
            limit=size + 1,
            with_payload=True,
            with_vectors=False,
        )
        stamps = {(point.payload or {}).get("metadata", {}).get("catalog") for point in points}
        return len(points) == size and stamps == {catalog}

    def index(self, products: list[Product], catalog: str = "") -> None:
        documents = [_product_to_document(p, catalog) for p in products]
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

    def max_dense_similarity(self, query_vector: list[float]) -> float:
        """Absolute cosine similarity of the best-matching product (0..1).

        Hybrid search returns *fused* (RRF) scores, which are relative — the top hit always
        scores near 1.0 even for a query the catalog cannot answer. That is why a floor on the
        fused score can never detect "no good match". This queries the dense vector directly so
        the score is an absolute, comparable similarity, which the no-match gate can threshold.

        Measured on this catalog: on-topic queries 0.47-0.55; off-topic (refrigerator, tyres,
        gibberish) 0.04-0.17 — hence the default threshold of 0.30.
        """
        response = self._qdrant().query_points(
            collection_name=self._settings.qdrant_collection,
            query=query_vector,
            using="",  # the unnamed dense vector (sparse is "langchain-sparse")
            limit=1,
            with_payload=False,
        )
        points = response.points
        return float(points[0].score) if points else 0.0
