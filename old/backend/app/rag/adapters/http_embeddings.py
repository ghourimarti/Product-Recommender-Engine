"""LangChain Embeddings backed by the self-hosted embedding service (Decision 12).

Lets the RAG stack consume embeddings over HTTP from our own service instead of a hosted
API. Subclasses LangChain's Embeddings ABC so langchain-qdrant accepts it.
"""
from __future__ import annotations

import httpx
from langchain_core.embeddings import Embeddings

from app.core.config import settings


class HTTPEmbeddings(Embeddings):
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = (base_url or settings.embedding_service_url).rstrip("/")
        self._timeout = timeout

    def _post(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(f"{self._base_url}/embed", json={"texts": texts}, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()["vectors"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._post(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._post([text])[0]
