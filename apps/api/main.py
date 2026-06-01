"""FastAPI serving app (Step 8): /health, /metrics, /recommend, /chat (SSE).

Clients (Qdrant store, DynamoDB history, LLM) are created lazily so /health and /metrics
work with no external dependencies. /chat streams recommendation cards first, then the
explanation token-by-token (Decision 8), and persists per-user history (Decision 1).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from core.auth import AuthError, user_id_from_token
from core.cache import RedisCache, make_redis
from core.config import get_settings
from core.embeddings import get_dense_embeddings
from core.history import DynamoChatHistory
from core.llm import astream_explanation, build_chat_model, rewrite_query
from core.models import ChatRequest, Product, RankingResult, RecommendRequest
from core.observability import configure_observability, get_langchain_callbacks
from core.ratelimit import RateLimiter, RateLimitExceeded
from core.resilience import CircuitBreaker
from core.security import redact_pii
from recommender.resilient import resilient_recommend
from retrieval.index import load_catalog
from retrieval.semantic_cache import SemanticCache
from retrieval.store import QdrantHybridStore

logger = logging.getLogger("p2.api")

REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency (s)", ["path"])


@lru_cache
def _store() -> QdrantHybridStore:
    return QdrantHybridStore()


@lru_cache
def _history() -> DynamoChatHistory:
    history = DynamoChatHistory()
    history.ensure_table()
    return history


@lru_cache
def _model() -> Any:
    return build_chat_model()


@lru_cache
def _cache() -> RedisCache:
    return RedisCache(make_redis())


@lru_cache
def _semantic_cache() -> SemanticCache:
    sc = SemanticCache()
    sc.ensure_collection()
    return sc


@lru_cache
def _embeddings() -> Any:
    return get_dense_embeddings()


@lru_cache
def _rate_limiter() -> RateLimiter:
    return RateLimiter.from_settings(_cache())


@lru_cache
def _callbacks() -> tuple[Any, ...]:
    return tuple(get_langchain_callbacks())


@lru_cache
def _catalog() -> list[Product]:
    return load_catalog()


@lru_cache
def _breaker() -> CircuitBreaker:
    return CircuitBreaker()


def require_user(authorization: str | None = Header(default=None)) -> str:
    """Authenticated user id from the Bearer JWT (Decision 9)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return user_id_from_token(authorization.split(" ", 1)[1])
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc


def rate_limited_user(user_id: str = Depends(require_user)) -> str:
    """Authenticated user id, after enforcing the per-user rate limit (Decisions 9, 20)."""
    try:
        _rate_limiter().check(user_id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    return user_id


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


app = FastAPI(title="P2 Product Recommender", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    LATENCY.labels(request.url.path).observe(time.perf_counter() - start)
    REQUESTS.labels(request.method, request.url.path, response.status_code).inc()
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/recommend")
def recommend_endpoint(
    req: RecommendRequest, user_id: str = Depends(rate_limited_user)
) -> RankingResult:
    """Sync, ranking-only path (no LLM) — the fast, 4-layer-cached recommendation list."""
    logger.info("recommend user=%s query=%s", user_id, redact_pii(req.query))  # PII-safe log
    return resilient_recommend(
        req.query,
        _store(),
        _cache(),
        _semantic_cache(),
        _embeddings(),
        _catalog(),
        k=req.k,
        breaker=_breaker(),
    )


@app.post("/chat")
async def chat_endpoint(
    req: ChatRequest, user_id: str = Depends(rate_limited_user)
) -> StreamingResponse:
    """SSE: emit recommendation cards, then stream the grounded explanation; persist history."""
    logger.info("chat user=%s session=%s query=%s", user_id, req.session_id, redact_pii(req.query))

    async def event_stream() -> AsyncIterator[str]:
        llm_on = get_settings().llm_enabled
        callbacks = list(_callbacks())
        model = _model() if llm_on else None
        history = _history().get_messages(user_id, req.session_id) if llm_on else []
        standalone = (
            rewrite_query(req.query, history, model, callbacks)
            if (history and llm_on)
            else req.query
        )

        result = resilient_recommend(
            standalone,
            _store(),
            _cache(),
            _semantic_cache(),
            _embeddings(),
            _catalog(),
            k=req.k,
            breaker=_breaker(),
        )
        yield _sse("recommendations", result.model_dump())
        if result.no_match or not result.products:
            yield _sse("done", {"no_match": True})
            return

        if not llm_on:  # kill-switch (Decision 20): cards served, LLM explanation disabled
            yield _sse("done", {"no_match": False, "degraded": True})
            return

        tokens: list[str] = []
        try:
            async for token in astream_explanation(standalone, result.products, model, callbacks):
                tokens.append(token)
                yield _sse("token", {"text": token})
        except Exception:  # all LLM providers failed -> static template (Decision 21)
            logger.warning("explanation generation failed; serving template", exc_info=True)
            yield _sse(
                "token",
                {"text": "Showing your top matches; explanations are temporarily unavailable."},
            )
            yield _sse("done", {"no_match": False, "degraded": True})
            return
        yield _sse("done", {"no_match": False})

        _history().add_message(user_id, req.session_id, "human", req.query)
        _history().add_message(user_id, req.session_id, "ai", "".join(tokens))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.delete("/history")
def delete_history(session_id: str, user_id: str = Depends(require_user)) -> dict[str, int]:
    """Clear one of the caller's chat sessions."""
    return {"deleted": _history().clear_session(user_id, session_id)}


@app.delete("/account")
def delete_account(user_id: str = Depends(require_user)) -> dict[str, int]:
    """Right-to-be-forgotten (Decision 24): delete ALL of the caller's data."""
    logger.info("account deletion requested user=%s", user_id)
    return {"deleted": _history().delete_user(user_id)}


@app.get("/account/export")
def export_account(user_id: str = Depends(require_user)) -> dict[str, Any]:
    """DSAR (Decision 24): export all of the caller's stored data."""
    return {"user_messages": _history().export_user(user_id)}


configure_observability(app)  # OTel traces + FastAPI instrumentation (best-effort)
