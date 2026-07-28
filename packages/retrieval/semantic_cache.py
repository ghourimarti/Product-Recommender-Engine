"""Semantic cache (L2): a dedicated Qdrant collection of query->result.

On lookup, the incoming query embedding is matched against cached query embeddings; if the
nearest is within the cosine threshold (and same catalog version), the cached result is
served, catching near-duplicate phrasings that an exact response cache misses. It reuses
Qdrant (ElastiCache OSS lacks vector search), so no new infra.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from core.config import Settings, get_settings
from core.models import RankingResult


class SemanticCacheLike(Protocol):
    def lookup(
        self, query_vector: list[float], version: str, threshold: float = 0.97
    ) -> RankingResult | None: ...

    def store(
        self, query_vector: list[float], version: str, query: str, result: RankingResult
    ) -> None: ...


class SemanticCache:
    """Qdrant-backed semantic cache for query->RankingResult."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._collection = "query_cache"
        self._client: Any = QdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key or None,
        )

    def ensure_collection(self) -> None:
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=self._settings.embedding_dim, distance=models.Distance.COSINE
                ),
            )

    def lookup(
        self, query_vector: list[float], version: str, threshold: float = 0.97
    ) -> RankingResult | None:
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=1,
            with_payload=True,
            query_filter=models.Filter(
                must=[models.FieldCondition(key="version", match=models.MatchValue(value=version))]
            ),
        )
        points = response.points
        if points and points[0].score >= threshold:
            return RankingResult.model_validate_json(points[0].payload["result"])
        return None

    def store(
        self, query_vector: list[float], version: str, query: str, result: RankingResult
    ) -> None:
        self._client.upsert(
            collection_name=self._collection,
            points=[
                models.PointStruct(
                    id=uuid.uuid4().hex,
                    vector=query_vector,
                    payload={
                        "version": version,
                        "query": query,
                        "result": result.model_dump_json(),
                    },
                )
            ],
        )
