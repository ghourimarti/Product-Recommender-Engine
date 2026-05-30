"""Per-identity rate limiting + kill-switch load shedding (Decision 20).

Fixed-window counter in Redis keyed by user (or client IP for anonymous). The kill-switch
sheds load (503) before counting, so it can stop new work under cost/incident pressure.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import Depends, Request

from app.api.deps import get_limiter
from app.core.config import settings
from app.core.exceptions import RateLimitError, ServiceUnavailableError
from app.core.security import Principal, get_current_user


class RateLimiter:
    def __init__(self, redis: Any) -> None:
        self._r = redis

    def allow(self, identity: str, limit: int, window: int) -> bool:
        bucket = int(time.time()) // window
        key = f"rl:{identity}:{bucket}"
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        count, _ = pipe.execute()
        return int(count) <= limit


async def rate_limit(
    request: Request,
    user: Principal = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_limiter),
) -> None:
    if not settings.rate_limit_enabled:
        return
    if settings.kill_switch:
        raise ServiceUnavailableError("Service temporarily degraded (load shedding)")
    identity = user.sub if not user.anonymous else (request.client.host if request.client else "anon")
    if not limiter.allow(identity, settings.rate_limit_requests, settings.rate_limit_window_seconds):
        raise RateLimitError("Rate limit exceeded")
