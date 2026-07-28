"""Integration tests for the API: /recommend and /chat (SSE).

Skips unless the required services/keys are present.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from tests.conftest import dynamodb_reachable, qdrant_reachable, redis_reachable

from api.main import app
from core.auth import mint_dev_token
from core.config import Settings, get_settings
from core.llm import available_providers
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def dev_auth() -> Iterator[Settings]:
    """Verify dev (HS256) tokens even when .env points at a real Clerk instance.

    These tests used to SKIP whenever CLERK_JWKS_URL was set — i.e. in the shipped
    configuration — so the API endpoints had zero executing coverage exactly where it mattered.
    Forcing the auth backend to dev tokens keeps the endpoints under test without weakening the
    production auth path (that is covered separately by the 401 tests).
    """
    dev = Settings(clerk_jwks_url="", auth_dev_bypass=False)
    patch = pytest.MonkeyPatch()
    patch.setattr("api.main.get_settings", lambda: dev)
    patch.setattr("core.auth.get_settings", lambda: dev)
    yield dev
    patch.undo()


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_dev_token('tester')}"}


@pytest.fixture(scope="module")
def client(dev_auth: Settings) -> TestClient:
    if not qdrant_reachable():
        pytest.skip(f"Qdrant not reachable at {get_settings().qdrant_url}")
    if not redis_reachable():
        pytest.skip("Redis not reachable (rate limiter)")
    if not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY not set (embeddings)")
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
    if not dynamodb_reachable():
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
