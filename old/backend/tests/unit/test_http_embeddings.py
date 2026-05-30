"""Step 10: HTTPEmbeddings parses the embedding-service response (mocked transport)."""
from __future__ import annotations

import httpx


def test_http_embeddings_parses_vectors(monkeypatch):
    from app.rag.adapters import http_embeddings

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/embed"
        n = len(httpx.QueryParams())  # noop to keep import used
        del n
        import json

        texts = json.loads(request.content)["texts"]
        return httpx.Response(200, json={"vectors": [[0.1, 0.2] for _ in texts], "model": "stub", "dim": 2})

    transport = httpx.MockTransport(handler)

    def fake_post(url, json, timeout):  # noqa: A002
        client = httpx.Client(transport=transport)
        return client.post(url, json=json, timeout=timeout)

    monkeypatch.setattr(http_embeddings.httpx, "post", fake_post)

    emb = http_embeddings.HTTPEmbeddings(base_url="http://embed")
    assert emb.embed_query("hi") == [0.1, 0.2]
    assert emb.embed_documents(["a", "b"]) == [[0.1, 0.2], [0.1, 0.2]]
