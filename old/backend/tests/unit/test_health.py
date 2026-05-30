"""Step 2: health/readiness probe behavior."""
from __future__ import annotations


def test_healthz_always_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_ready(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["rag"] is True


def test_readyz_not_ready_returns_503(client_not_ready):
    r = client_not_ready.get("/readyz")
    assert r.status_code == 503
    assert r.json()["rag"] is False


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
