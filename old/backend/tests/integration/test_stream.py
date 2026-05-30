"""Step 9: SSE streaming endpoint emits token/citations/done events in order."""
from __future__ import annotations


def test_stream_emits_sse_events(client):
    with client.stream("POST", "/chat/stream", json={"message": "earbuds"}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = "".join(r.iter_text())

    assert "event: citations" in body
    assert "event: token" in body
    assert "event: done" in body
    assert "earbuds" in body  # the streamed token content


def test_stream_error_event_when_not_ready(client_not_ready):
    with client_not_ready.stream("POST", "/chat/stream", json={"message": "hi"}) as r:
        body = "".join(r.iter_text())
    assert "event: error" in body
