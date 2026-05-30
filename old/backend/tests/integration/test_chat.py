"""Step 2: chat endpoint contract (parity with the demo's /get, now JSON)."""
from __future__ import annotations


def test_chat_returns_answer(client):
    r = client.post("/chat", json={"message": "best wireless earbuds?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "echo: best wireless earbuds?"
    assert body["session_id"]
    assert body["citations"] == []


def test_chat_echoes_session_id(client):
    r = client.post("/chat", json={"message": "hi", "session_id": "sid-42"})
    assert r.json()["session_id"] == "sid-42"


def test_chat_validation_rejects_empty(client):
    r = client.post("/chat", json={"message": ""})
    assert r.status_code == 422  # pydantic min_length


def test_chat_503_when_not_ready(client_not_ready):
    r = client_not_ready.post("/chat", json={"message": "hi"})
    assert r.status_code == 503
    assert r.json()["error"] == "service_unavailable"
