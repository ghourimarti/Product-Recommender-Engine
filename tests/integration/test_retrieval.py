"""Integration test: real Qdrant + real OpenAI embeddings (Step 3).

Skips unless OPENAI_API_KEY is set and Qdrant is reachable on localhost:6333.
"""

from __future__ import annotations

import socket

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
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect(("localhost", 6333))
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
        pytest.skip("Qdrant not reachable on localhost:6333")
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
