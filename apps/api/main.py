"""FastAPI serving app (Step 8): /health, /metrics, /recommend, /chat (SSE).

Clients (Qdrant store, DynamoDB history, LLM) are created lazily so /health and /metrics
work with no external dependencies. /chat streams recommendation cards first, then the
explanation token-by-token (Decision 8), and persists per-user history (Decision 1).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from core.history import DynamoChatHistory
from core.llm import astream_explanation, build_chat_model, rewrite_query
from core.models import ChatRequest, RankingResult, RecommendRequest
from recommender.service import recommend
from retrieval.store import QdrantHybridStore

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


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


app = FastAPI(title="P2 Product Recommender", version="0.1.0")


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
def recommend_endpoint(req: RecommendRequest) -> RankingResult:
    """Sync, ranking-only path (no LLM) — the fast recommendation list."""
    return recommend(req.query, _store(), k=req.k)


@app.post("/chat")
async def chat_endpoint(req: ChatRequest) -> StreamingResponse:
    """SSE: emit recommendation cards, then stream the grounded explanation; persist history."""

    async def event_stream() -> AsyncIterator[str]:
        model = _model()
        history = _history().get_messages(req.user_id, req.session_id)
        standalone = rewrite_query(req.query, history, model) if history else req.query

        result = recommend(standalone, _store(), k=req.k)
        yield _sse("recommendations", result.model_dump())
        if result.no_match or not result.products:
            yield _sse("done", {"no_match": True})
            return

        tokens: list[str] = []
        async for token in astream_explanation(standalone, result.products, model):
            tokens.append(token)
            yield _sse("token", {"text": token})
        yield _sse("done", {"no_match": False})

        _history().add_message(req.user_id, req.session_id, "human", req.query)
        _history().add_message(req.user_id, req.session_id, "ai", "".join(tokens))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
