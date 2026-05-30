"""Prometheus metrics + request middleware (Decision 13/17)."""
from __future__ import annotations

import time

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["method", "path"])
LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens", ["model", "type"])
LLM_COST_USD = Counter("llm_cost_usd_total", "LLM cost in USD", ["model"])
CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["kind"])


class MetricsMiddleware:
    """Pure-ASGI middleware (NOT BaseHTTPMiddleware, which buffers and breaks SSE streaming).

    Records request count + latency without touching the response body, so token streaming
    passes through untouched.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            path = getattr(route, "path", scope.get("path", "unknown"))
            REQUEST_COUNT.labels(scope["method"], path, status["code"]).inc()
            REQUEST_LATENCY.labels(scope["method"], path).observe(time.perf_counter() - start)
