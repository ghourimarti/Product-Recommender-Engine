"""Step 13: chat route enforces rate limit (429) and kill-switch (503)."""
from __future__ import annotations

from app.core.config import settings


def test_chat_returns_429_over_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)

    assert client.post("/chat", json={"message": "a"}).status_code == 200
    assert client.post("/chat", json={"message": "b"}).status_code == 200
    r = client.post("/chat", json={"message": "c"})
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"


def test_kill_switch_sheds_load(client, monkeypatch):
    monkeypatch.setattr(settings, "kill_switch", True)
    r = client.post("/chat", json={"message": "a"})
    assert r.status_code == 503
    assert r.json()["error"] == "service_unavailable"
