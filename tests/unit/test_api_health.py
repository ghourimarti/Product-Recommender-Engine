"""Unit tests for the API health/metrics endpoints (Step 8). No external services."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

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


def test_recommend_requires_auth() -> None:
    # No bearer token -> rejected before any external service is touched (Decision 9).
    response = client.post("/recommend", json={"query": "x", "k": 3})
    assert response.status_code == 401


def test_cors_allows_frontend_origin() -> None:
    # Browser at the Next.js origin must be allowed cross-origin (Decision 18).
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
