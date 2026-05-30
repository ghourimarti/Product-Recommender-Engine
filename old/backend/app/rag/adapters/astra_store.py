"""AstraDB vector-store provider (the Step-1 backend, now behind the interface).

Absorbs the old ``DataIngestor``. Heavy imports are deferred to method bodies so importing
this module never forces LangChain/Astra to load (keeps the app bootable + tests light).
This is the adapter that Step 4 replaces with a Qdrant equivalent.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


class AstraVectorStoreProvider:
    def __init__(self) -> None:
        self._store: Any = None

    def _build_store(self) -> Any:
        from langchain_astradb import AstraDBVectorStore
        from langchain_huggingface import HuggingFaceEndpointEmbeddings

        embedding = HuggingFaceEndpointEmbeddings(model=settings.embedding_model)
        return AstraDBVectorStore(
            embedding=embedding,
            collection_name=settings.vector_collection_name,
            api_endpoint=settings.astra_db_api_endpoint,
            token=settings.astra_db_application_token,
            namespace=settings.astra_db_keyspace,
        )

    def get_vectorstore(self) -> Any:
        if self._store is None:
            self._store = self._build_store()
            logger.info("astra_store_initialized")
        return self._store

    def add_documents(self, docs: list[Any]) -> None:
        self.get_vectorstore().add_documents(docs)
        logger.info("astra_documents_added", extra={"count": len(docs)})
