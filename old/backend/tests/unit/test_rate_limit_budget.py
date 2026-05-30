"""Step 13: rate limiter + token budget logic (fakeredis)."""
from __future__ import annotations

import fakeredis

from app.core.budget import TokenBudget
from app.core.rate_limiter import RateLimiter


def test_rate_limiter_allows_then_blocks():
    rl = RateLimiter(fakeredis.FakeRedis())
    assert rl.allow("u1", limit=3, window=60) is True   # 1
    assert rl.allow("u1", limit=3, window=60) is True   # 2
    assert rl.allow("u1", limit=3, window=60) is True   # 3
    assert rl.allow("u1", limit=3, window=60) is False  # 4 -> blocked


def test_rate_limiter_isolated_per_identity():
    rl = RateLimiter(fakeredis.FakeRedis())
    assert rl.allow("a", 1, 60) is True
    assert rl.allow("a", 1, 60) is False
    assert rl.allow("b", 1, 60) is True  # different identity, own bucket


def test_budget_consume_and_over():
    b = TokenBudget(fakeredis.FakeRedis())
    assert b.over("u1", limit=100) is False
    b.consume("u1", 60)
    assert b.used("u1") == 60
    assert b.over("u1", limit=100) is False
    b.consume("u1", 50)
    assert b.over("u1", limit=100) is True  # 110 >= 100
