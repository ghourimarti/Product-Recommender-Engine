"""Embedding-service contract test (stub mode — no model download)."""
from __future__ import annotations

import os

os.environ["EMBEDDING_STUB"] = "1"
os.environ["EMBEDDING_DIM"] = "32"

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_embed_shape_and_determinism():
    r = client.post("/embed", json={"texts": ["hello", "world"]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["vectors"]) == 2
    assert body["dim"] == 32
    # deterministic: same text -> same vector
    r2 = client.post("/embed", json={"texts": ["hello"]})
    assert r2.json()["vectors"][0] == body["vectors"][0]


def test_embed_rejects_empty():
    r = client.post("/embed", json={"texts": []})
    assert r.status_code == 422
