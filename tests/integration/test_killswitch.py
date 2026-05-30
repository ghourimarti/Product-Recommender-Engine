"""Integration test for the LLM kill-switch (Step 12).

With LLM_ENABLED=false, /chat must still serve recommendation cards but emit NO LLM tokens.
Needs Qdrant + Redis + OPENAI_API_KEY (retrieval/cache still run; only the LLM is disabled).
"""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from core.auth import mint_dev_token
from core.config import get_settings


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


@pytest.mark.integration
def test_chat_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (_reachable(6333) and _reachable(6379)):
        pytest.skip("needs Qdrant + Redis")
    if not get_settings().openai_api_key:
        pytest.skip("needs OPENAI_API_KEY (embeddings)")
    if get_settings().clerk_jwks_url:
        pytest.skip("Clerk configured; dev token n/a")

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
