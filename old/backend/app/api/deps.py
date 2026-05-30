"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Request

from app.rag.service import RagService


def get_rag_service(request: Request) -> RagService:
    """Return the process-wide RagService held on app state.

    Overridable in tests via ``app.dependency_overrides[get_rag_service]``.
    """
    return request.app.state.rag_service


def get_limiter():
    """RateLimiter dependency (overridable in tests with a fakeredis-backed instance)."""
    from app.cache.redis_cache import get_redis
    from app.core.rate_limiter import RateLimiter

    return RateLimiter(get_redis())


def get_budget():
    """TokenBudget dependency (overridable in tests)."""
    from app.cache.redis_cache import get_redis
    from app.core.budget import TokenBudget

    return TokenBudget(get_redis())
