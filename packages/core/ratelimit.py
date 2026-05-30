"""Per-user rate limiting + daily quota (Decisions 9, 20) via Redis fixed-window counters."""

from __future__ import annotations

from dataclasses import dataclass

from core.cache import RedisCache
from core.config import get_settings


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after = retry_after_seconds
        super().__init__(f"rate limit exceeded; retry after {retry_after_seconds}s")


@dataclass
class RateLimiter:
    cache: RedisCache
    per_minute: int = 30
    per_day: int = 500

    @classmethod
    def from_settings(cls, cache: RedisCache) -> RateLimiter:
        settings = get_settings()
        return cls(cache, settings.rate_limit_per_minute, settings.rate_limit_per_day)

    def check(self, user_id: str) -> None:
        """Raise RateLimitExceeded if the user is over the minute or daily limit."""
        if self.cache.incr_window(f"rl:{user_id}:min", 60) > self.per_minute:
            raise RateLimitExceeded(60)
        if self.cache.incr_window(f"rl:{user_id}:day", 86400) > self.per_day:
            raise RateLimitExceeded(86400)
