"""Integration test: real Qdrant + real OpenAI embeddings.

Skips unless OPENAI_API_KEY is set and Qdrant is reachable at QDRANT_URL.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import pytest

from core.config import get_settings
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

pytestmark = pytest.mark.integration

QUERIES = [
    "headphones with the best bass",
    "long battery life earbuds for calls",
    "cheap bluetooth neckband",
]


def _qdrant_reachable() -> bool:
    # Env-driven: whatever QDRANT_URL points at (default 2001 per .env.example).
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
def indexed_store() -> QdrantHybridStore:
    if not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")
    if not _qdrant_reachable():
        pytest.skip(f"Qdrant not reachable at {get_settings().qdrant_url}")
    store = QdrantHybridStore()
    store.index(load_catalog())
    return store


@pytest.mark.parametrize("query", QUERIES)
def test_search_returns_ranked_products(indexed_store: QdrantHybridStore, query: str) -> None:
    results = indexed_store.search(query, k=3)
    assert len(results) == 3
    assert all(r.product_id and r.title for r in results)
    scores = [r.semantic_score for r in results]
    assert scores == sorted(scores, reverse=True)  # results ranked by score, descending
