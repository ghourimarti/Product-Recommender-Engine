"""FastAPI serving app: /health, /metrics, /recommend, /chat (SSE).

Clients (Qdrant store, DynamoDB history, LLM) are created lazily so /health and /metrics
work with no external dependencies. /chat streams recommendation cards first, then the
explanation token-by-token, and persists per-user history.
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
from core.models import AggregatorResult, ChatRequest, Product, RankingResult, RecommendRequest
from core.observability import configure_observability, get_langchain_callbacks
from core.ratelimit import RateLimiter, RateLimitExceeded
from core.resilience import CircuitBreaker
from core.security import (
    SAFE_EXPLANATION,
    clean_user_text,
    output_violates_policy,
    redact_pii,
)
from recommender.aggregator import aggregate, aggregate_stream
from recommender.resilient import resilient_recommend
from retrieval.index import load_catalog
from retrieval.semantic_cache import SemanticCache
from retrieval.store import QdrantHybridStore

logger = logging.getLogger("p2.api")

REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency (s)", ["path"])

# Characters of generated text held back before release, so a system-prompt leak is caught by the
# output guardrail before any of it reaches the client.
#
# The soundness floor is derived in core.security (MIN_GUARD_HOLDBACK = longest leak fragment - 1,
# currently 31); anything at or above it makes it impossible for the start of a leak to be
# released before the leak completes and is detected. 200 is chosen well above that floor so the
# guarantee survives someone adding a longer fragment, and so a paraphrased leak that only trips
# the regex late still has room. test_security asserts GUARD_HOLDBACK >= MIN_GUARD_HOLDBACK, so
# the invariant fails in CI rather than silently in production.
#
# Cost of the margin: the last 200 characters of every answer arrive in one chunk at the end
# instead of streaming. Explanations are capped at MAX_OUTPUT_TOKENS (600), so this trades the
# tail of the response for the guarantee -- deliberately, because a partially-streamed system
# prompt cannot be recalled once it is on the client.
GUARD_HOLDBACK = 200


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


def dev_bypass_allowed(settings: Any) -> bool:
    """Anonymous callers may assume the `dev-user` identity ONLY when all three hold.

    Fail CLOSED: a missing/empty CLERK_JWKS_URL alone must never open the API. Requiring an
    explicit opt-in (auth_dev_bypass) *and* app_env == "local" means a misconfigured deployment
    returns 401 instead of silently serving every anonymous caller as one shared identity.
    """
    return not settings.clerk_jwks_url and settings.app_env == "local" and settings.auth_dev_bypass


def assert_auth_config_sane(settings: Any) -> None:
    """Fail fast at startup rather than serve a non-local environment with no auth."""
    if settings.app_env != "local" and not settings.clerk_jwks_url:
        raise RuntimeError(
            f"APP_ENV={settings.app_env!r} but CLERK_JWKS_URL is empty — refusing to start "
            "an unauthenticated API. Set CLERK_JWKS_URL, or run with APP_ENV=local."
        )


def require_user(authorization: str | None = Header(default=None)) -> str:
    """Authenticated user id from the Bearer JWT. Fails closed."""
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        if dev_bypass_allowed(settings):
            return "dev-user"
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
    query = clean_user_text(req.query)  # PII redacted + injection neutralised at the edge
    logger.info("recommend user=%s query=%s", user_id, redact_pii(req.query))
    return resilient_recommend(
        query,
        _store(),
        _cache(),
        _semantic_cache(),
        _embeddings(),
        _catalog(),
        k=req.k,
        breaker=_breaker(),
    )


@app.post("/aggregate")
def aggregate_endpoint(
    req: RecommendRequest, user_id: str = Depends(rate_limited_user)
) -> AggregatorResult:
    """Live shopping aggregator: SerpApi search -> rank -> grounded reasons (cached)."""
    query = clean_user_text(req.query)
    logger.info("aggregate user=%s query=%s", user_id, redact_pii(req.query))
    return aggregate(query, _cache(), _model(), k=req.k, callbacks=list(_callbacks()))


@app.post("/aggregate/stream")
async def aggregate_stream_endpoint(
    req: RecommendRequest, user_id: str = Depends(rate_limited_user)
) -> StreamingResponse:
    """SSE: emit ranked CARDS as soon as the search returns, then the grounded reasons.

    The blocking /aggregate made the user stare at a skeleton for the search AND the LLM (cold:
    2.94s, breaching the p95 < 2s NFR). Here the cards land ~1-1.5s earlier and the reasons fill
    in afterwards — which is also what makes the SSE path something the UI actually uses.
    """
    query = clean_user_text(req.query)
    logger.info("aggregate.stream user=%s query=%s", user_id, redact_pii(req.query))

    async def event_stream() -> AsyncIterator[str]:
        for stage, result in aggregate_stream(
            query, _cache(), _model(), k=req.k, callbacks=list(_callbacks())
        ):
            yield _sse(stage, result.model_dump())
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
        query = clean_user_text(req.query)  # PII + injection scrubbed before ANY prompt/trace
        history = _history().get_messages(user_id, req.session_id) if llm_on else []
        standalone = (
            rewrite_query(query, history, model, callbacks) if (history and llm_on) else query
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

        if not llm_on:  # kill-switch: cards served, LLM explanation disabled
            yield _sse("done", {"no_match": False, "degraded": True})
            return

        # Output guardrail. Tokens are held back by GUARD_HOLDBACK characters so a
        # system-prompt leak is detected BEFORE any of it is released to the client. On violation
        # we stop generating and replace the answer with safe text.
        buffer, released, blocked = "", 0, False
        try:
            async for token in astream_explanation(standalone, result.products, model, callbacks):
                buffer += token
                if output_violates_policy(buffer):
                    blocked = True
                    break
                safe_upto = max(0, len(buffer) - GUARD_HOLDBACK)
                if safe_upto > released:
                    yield _sse("token", {"text": buffer[released:safe_upto]})
                    released = safe_upto
        except Exception:  # all LLM providers failed -> static template
            logger.warning("explanation generation failed; serving template", exc_info=True)
            yield _sse(
                "token",
                {"text": "Showing your top matches; explanations are temporarily unavailable."},
            )
            yield _sse("done", {"no_match": False, "degraded": True})
            return

        if blocked:
            logger.warning("guardrail: blocked prompt-leaking explanation user=%s", user_id)
            yield _sse("guardrail", {"blocked": True, "reason": "prompt_leak"})
            yield _sse("token", {"text": SAFE_EXPLANATION})
            yield _sse("done", {"no_match": False, "degraded": True})
            return

        yield _sse("token", {"text": buffer[released:]})  # release the held-back tail
        yield _sse("done", {"no_match": False})

        _history().add_message(user_id, req.session_id, "human", query)
        _history().add_message(user_id, req.session_id, "ai", buffer)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.delete("/history")
def delete_history(session_id: str, user_id: str = Depends(require_user)) -> dict[str, int]:
    """Clear one of the caller's chat sessions."""
    return {"deleted": _history().clear_session(user_id, session_id)}


@app.delete("/account")
def delete_account(user_id: str = Depends(require_user)) -> dict[str, int]:
    """Right-to-be-forgotten: delete all of the caller's data."""
    logger.info("account deletion requested user=%s", user_id)
    return {"deleted": _history().delete_user(user_id)}


@app.get("/account/export")
def export_account(user_id: str = Depends(require_user)) -> dict[str, Any]:
    """Export all of the caller's stored data (DSAR)."""
    return {"user_messages": _history().export_user(user_id)}


configure_observability(app)  # logging + OTel traces + FastAPI instrumentation
assert_auth_config_sane(get_settings())  # refuse to boot a non-local env with auth disabled
