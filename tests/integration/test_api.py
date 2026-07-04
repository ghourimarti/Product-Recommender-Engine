"""Integration tests for the API: /recommend and /chat (SSE) (Step 8).

Skips unless the required services/keys are present.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.auth import mint_dev_token
from core.config import get_settings
from core.llm import available_providers
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

pytestmark = pytest.mark.integration


def _reachable_url(url: str, default_port: int) -> bool:
    """Probe host:port derived from a URL — env-driven (see .env.example port scheme)."""
    parsed = urlparse(url)
    host, port = parsed.hostname or "localhost", parsed.port or default_port
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_dev_token('tester')}"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    s = get_settings()
    if not _reachable_url(s.qdrant_url, default_port=2001):
        pytest.skip(f"Qdrant not reachable at {s.qdrant_url}")
    if not _reachable_url(s.redis_url, default_port=2004):
        pytest.skip("Redis not reachable (rate limiter)")
    if not s.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set (embeddings)")
    if s.clerk_jwks_url:
        pytest.skip("Clerk JWKS configured; dev tokens not valid")
    QdrantHybridStore().index(load_catalog())  # ensure the collection exists for the API
    return TestClient(app)


def test_recommend_endpoint(client: TestClient) -> None:
    response = client.post(
        "/recommend", json={"query": "good bass headphones", "k": 3}, headers=_auth()
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["products"]) >= 1
    assert body["products"][0]["product_id"]
    assert body["no_match"] is False


def test_chat_sse_stream(client: TestClient) -> None:
    if not available_providers(get_settings()):
        pytest.skip("no LLM provider key")
    if not _reachable_url(get_settings().dynamodb_endpoint, default_port=2003):
        pytest.skip(f"DynamoDB-local not reachable at {get_settings().dynamodb_endpoint}")
    response = client.post(
        "/chat",
        json={"query": "good bass headphones", "session_id": "t", "k": 3},
        headers=_auth(),
    )
    assert response.status_code == 200
    text = response.text
    assert "event: recommendations" in text
    assert "event: token" in text
    assert "event: done" in text
