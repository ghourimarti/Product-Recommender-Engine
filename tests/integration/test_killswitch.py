"""Integration test for the LLM kill-switch.

With LLM_ENABLED=false, /chat must still serve recommendation cards but emit NO LLM tokens.
Needs Qdrant + Redis + OPENAI_API_KEY (retrieval/cache still run; only the LLM is disabled).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from tests.conftest import qdrant_reachable, redis_reachable

from core.auth import mint_dev_token
from core.config import get_settings


@pytest.mark.integration
def test_chat_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (qdrant_reachable() and redis_reachable()):
        pytest.skip("needs Qdrant + Redis")
    if not get_settings().openai_api_key:
        pytest.skip("needs OPENAI_API_KEY (embeddings)")
    # Force dev-token auth so this runs even when .env points at real Clerk (it used to skip,
    # leaving the kill-switch with zero executing coverage).
    monkeypatch.setenv("CLERK_JWKS_URL", "")
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()
    try:
        from retrieval.index import load_catalog
        from retrieval.store import QdrantHybridStore

        QdrantHybridStore().index(load_catalog())
        from api.main import app

        client = TestClient(app)
        response = client.post(
            "/chat",
            json={"query": "good bass headphones", "session_id": "ks", "k": 2},
            headers={"Authorization": f"Bearer {mint_dev_token('ks-user')}"},
        )
        assert response.status_code == 200
        assert "event: recommendations" in response.text  # cards still served
        assert "event: token" not in response.text  # LLM disabled -> no streamed tokens
        assert "degraded" in response.text
    finally:
        get_settings.cache_clear()  # restore real settings for other tests
