"""Unit tests for the API health/metrics endpoints. No external services."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import Settings, get_settings

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_counts_requests() -> None:
    client.get("/health")  # generate at least one counted request
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text  # real request counter (fixes demo's bug)


def test_recommend_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    # In dev mode (clerk_jwks_url unset) an unauthenticated request is granted the
    # `dev-user` identity so the frontend works without a token. This test asserts the
    # *production* contract: with Clerk auth on, a missing token is a hard 401 — raised
    # at the auth gate, BEFORE any LLM/embedding client is constructed (which would
    # otherwise fail with no OPENAI_API_KEY in CI). See require_user in api.main.
    prod_settings = Settings(clerk_jwks_url="https://example.test/jwks.json")
    # require_user resolves settings via api.main's bound `get_settings` name, so patch there.
    monkeypatch.setattr("api.main.get_settings", lambda: prod_settings)

    response = client.post("/recommend", json={"query": "x", "k": 3})
    assert response.status_code == 401


def test_cors_allows_frontend_origin() -> None:
    # Browser at the Next.js origin must be allowed cross-origin.
    # Origin is env-driven (see CORS_ORIGINS in .env / .env.example — first entry
    # is the web frontend, default http://localhost:2012).
    origin = get_settings().cors_origins.split(",")[0].strip()
    response = client.get("/health", headers={"Origin": origin})
    assert response.headers.get("access-control-allow-origin") == origin
