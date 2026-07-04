"""Integration test: end-to-end chat with a real LLM + Qdrant (Step 6).

Skips unless an LLM key is configured and Qdrant is reachable.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import pytest

from core.config import get_settings
from core.llm import available_providers
from recommender.chat import chat
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

pytestmark = pytest.mark.integration


def _qdrant_reachable() -> bool:
    # Probe whatever host:port QDRANT_URL points at — port scheme is env-driven
    # (2001 by default in .env; still works if you override it).
    parsed = urlparse(get_settings().qdrant_url)
    host, port = parsed.hostname or "localhost", parsed.port or 2001
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


@pytest.fixture(scope="module")
def store() -> QdrantHybridStore:
    if not available_providers(get_settings()):
        pytest.skip("no LLM provider key configured")
    if not _qdrant_reachable():
        pytest.skip(f"Qdrant not reachable at {get_settings().qdrant_url}")
    s = QdrantHybridStore()
    s.index(load_catalog())
    return s


def test_chat_returns_grounded_recommendations(store: QdrantHybridStore) -> None:
    response = chat("headphones with good bass", [], store, k=3)
    catalog_ids = {p.product_id for p in load_catalog()}

    assert response.no_match is False
    assert 1 <= len(response.items) <= 3
    assert response.summary.strip()
    assert all(item.product_id in catalog_ids for item in response.items)
    assert response.items[0].reason.strip()  # the top pick must be explained
