"""Chat caching: exact response cache + semantic cache (Decision 10).

The biggest cost/latency lever for repeated product questions. Two layers:
  - response cache: exact-match on the normalized question (keyed by catalog_version + TTL).
  - semantic cache: embed the question and reuse a prior answer when cosine similarity
    exceeds a threshold.

Invalidation: TTL + a catalog_version prefix bumped on re-index. The semantic index is a
capped Redis list with brute-force cosine — fine for a bounded cache; the scale upgrade is
Redis vector search (redis-stack), noted in the build-spec.

Caching is keyed on the question only, so it targets standalone/first-turn product
questions; callers pass ``skip=True`` when a session already has history (history-aware
answers are session-specific and must not be cross-served).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger
from app.schemas.chat import ChatResponse

logger = get_logger(__name__)


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class ChatCache:
    def __init__(self, redis: Any, embedder: Any | None = None) -> None:
        self._r = redis
        self._embedder = embedder
        self._cv = settings.catalog_version
        self._ttl = settings.cache_ttl_seconds

    def _resp_key(self, message: str) -> str:
        h = hashlib.sha256(_norm(message).encode()).hexdigest()
        return f"resp:{self._cv}:{h}"

    @property
    def _sem_index(self) -> str:
        return f"sem:{self._cv}:index"

    def get(self, message: str) -> ChatResponse | None:
        # Degrade, don't fail (D21): a Redis outage must not break answering — bypass cache.
        try:
            raw = self._r.get(self._resp_key(message))
            if raw:
                logger.info("cache_hit", extra={"kind": "exact"})
                return self._load(raw)

            if settings.semantic_cache_enabled and self._embedder is not None:
                vec = self._embedder.embed_query(message)
                for entry in self._r.lrange(self._sem_index, 0, -1):
                    rec = json.loads(entry)
                    if _cosine(vec, rec["vec"]) >= settings.semantic_cache_threshold:
                        raw = self._r.get(f"resp:{self._cv}:{rec['h']}")
                        if raw:
                            logger.info("cache_hit", extra={"kind": "semantic"})
                            return self._load(raw)
        except Exception:  # noqa: BLE001
            logger.warning("cache_get_failed_degrading")
        return None

    def set(self, message: str, response: ChatResponse) -> None:
        try:
            key = self._resp_key(message)
            self._r.setex(key, self._ttl, response.model_dump_json())
            if settings.semantic_cache_enabled and self._embedder is not None:
                h = key.split(":")[-1]
                self._r.rpush(self._sem_index, json.dumps({"h": h, "vec": self._embedder.embed_query(message)}))
                self._r.ltrim(self._sem_index, -settings.semantic_cache_max_entries, -1)
        except Exception:  # noqa: BLE001
            logger.warning("cache_set_failed_degrading")

    @staticmethod
    def _load(raw: bytes | str) -> ChatResponse:
        data = json.loads(raw)
        data["cached"] = True
        return ChatResponse(**data)
