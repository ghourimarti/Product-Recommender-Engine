"""Caching primitives (Decision 10): Redis cache, in-proc TTL (L0), embedding cache (L1).

Layers (see recommender.cached for L2/L3 orchestration):
- L0  in-process TTL memo (catalog version) — avoids a Redis round-trip per request.
- L1  Redis embedding cache — query vectors keyed by hash(model+text).
- L3  Redis response cache — keyed by hash(version+k+normalized_query).
Invalidation: bump ``catalog:version`` -> all version-tagged keys miss.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from typing import Any

import redis
from prometheus_client import Counter

from core.config import Settings, get_settings

CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["layer"])
CACHE_MISSES = Counter("cache_misses_total", "Cache misses", ["layer"])

CATALOG_VERSION_KEY = "catalog:version"
EMBED_TTL_SECONDS = 30 * 24 * 3600


def make_redis(settings: Settings | None = None) -> Any:
    settings = settings or get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def hash_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


class InProcessTTL:
    """Tiny in-process TTL cache (L0)."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._store.clear()


class RedisCache:
    """Thin JSON-friendly wrapper over a redis client (or fakeredis in tests)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    # Cache ops degrade gracefully (Decision 21): Redis failures must never break a request.
    def get(self, key: str) -> str | None:
        try:
            value = self._client.get(key)
        except Exception:
            return None
        return None if value is None else str(value)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        with contextlib.suppress(Exception):  # cache writes must never break a request
            self._client.set(key, value, ex=ttl_seconds)

    def incr(self, key: str) -> int:
        try:
            return int(self._client.incr(key))
        except Exception:
            return 0

    def incr_window(self, key: str, ttl_seconds: int) -> int:
        """Fixed-window counter; on Redis failure returns 0 (rate limiting fails open)."""
        try:
            value = int(self._client.incr(key))
            if value == 1:
                self._client.expire(key, ttl_seconds)
            return value
        except Exception:
            return 0

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.set(key, json.dumps(value), ttl_seconds)


_VERSION_MEMO = InProcessTTL(60.0)  # L0


def clear_version_memo() -> None:
    """Reset the L0 version memo (used by tests)."""
    _VERSION_MEMO.clear()


def get_catalog_version(cache: RedisCache) -> str:
    memoized = _VERSION_MEMO.get("v")
    if memoized is not None:
        CACHE_HITS.labels("catalog_l0").inc()
        return str(memoized)
    CACHE_MISSES.labels("catalog_l0").inc()
    version = cache.get(CATALOG_VERSION_KEY)
    if version is None:
        cache.set(CATALOG_VERSION_KEY, "1")  # persist so the next bump (incr) yields "2"
        version = "1"
    _VERSION_MEMO.set("v", version)
    return version


def bump_catalog_version(cache: RedisCache) -> str:
    version = str(cache.incr(CATALOG_VERSION_KEY))
    _VERSION_MEMO.set("v", version)  # keep L0 consistent after an explicit bump
    return version


def cached_embed_query(text: str, embeddings: Any, cache: RedisCache, model: str) -> list[float]:
    """L1: embed the query, caching the vector in Redis by hash(model+text)."""
    key = "emb:" + hash_key(model, text)
    cached = cache.get_json(key)
    if cached is not None:
        CACHE_HITS.labels("embedding").inc()
        return [float(x) for x in cached]
    CACHE_MISSES.labels("embedding").inc()
    vector = [float(x) for x in embeddings.embed_query(text)]
    cache.set_json(key, vector, EMBED_TTL_SECONDS)
    return vector
