"""Unit tests for the per-user rate limiter using fakeredis."""

from __future__ import annotations

import fakeredis
import pytest

from core.cache import RedisCache
from core.ratelimit import RateLimiter, RateLimitExceeded


def _cache() -> RedisCache:
    return RedisCache(fakeredis.FakeRedis(decode_responses=True))


def test_under_limit_passes() -> None:
    limiter = RateLimiter(_cache(), per_minute=3, per_day=100)
    for _ in range(3):
        limiter.check("u")  # no raise


def test_over_minute_limit_raises() -> None:
    limiter = RateLimiter(_cache(), per_minute=2, per_day=100)
    limiter.check("u")
    limiter.check("u")
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("u")
    assert exc.value.retry_after == 60


def test_limits_are_per_user() -> None:
    limiter = RateLimiter(_cache(), per_minute=1, per_day=100)
    limiter.check("alice")
    limiter.check("bob")  # separate bucket
    with pytest.raises(RateLimitExceeded):
        limiter.check("alice")
