"""Integration tests for the API: /recommend and /chat (SSE) (Step 8).

Skips unless the required services/keys are present.
"""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import get_settings
from core.llm import available_providers
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

pytestmark = pytest.mark.integration


def _reachable(port: int) -> bool:
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect(("localhost", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


@pytest.fixture(scope="module")
def client() -> TestClient:
    if not _reachable(6333):
        pytest.skip("Qdrant not reachable on localhost:6333")
    if not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY not set (embeddings)")
    QdrantHybridStore().index(load_catalog())  # ensure the collection exists for the API
    return TestClient(app)


def test_recommend_endpoint(client: TestClient) -> None:
    response = client.post("/recommend", json={"query": "good bass headphones", "k": 3})
    assert response.status_code == 200
    body = response.json()
    assert len(body["products"]) >= 1
    assert body["products"][0]["product_id"]
    assert body["no_match"] is False


def test_chat_sse_stream(client: TestClient) -> None:
    if not available_providers(get_settings()):
        pytest.skip("no LLM provider key")
    if not _reachable(8000):
        pytest.skip("DynamoDB-local not reachable on localhost:8000")
    response = client.post(
        "/chat",
        json={"query": "good bass headphones", "session_id": "t", "user_id": "tester", "k": 3},
    )
    assert response.status_code == 200
    text = response.text
    assert "event: recommendations" in text
    assert "event: token" in text
    assert "event: done" in text
