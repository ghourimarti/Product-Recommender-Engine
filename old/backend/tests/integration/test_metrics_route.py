"""Step 17: a chat call surfaces request + LLM token metrics on /metrics."""
from __future__ import annotations


def test_metrics_expose_request_and_token_counters(client):
    client.post("/chat", json={"message": "best earbuds?"})
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "llm_tokens_total" in body
