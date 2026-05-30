"""Redis client factory (Decision 10)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import settings


@lru_cache
def get_redis() -> Any:
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=False)
