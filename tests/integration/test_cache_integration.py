"""Integration tests for the cache layers against real Redis + Qdrant (Step 9)."""

from __future__ import annotations

import socket
import uuid

import pytest

from core.cache import RedisCache, clear_version_memo, make_redis
from core.config import get_settings
from core.embeddings import get_dense_embeddings
from core.models import RankedProduct, RankingResult
from recommender.cached import cached_recommend
from retrieval.index import load_catalog
from retrieval.semantic_cache import SemanticCache
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


def _ranked(product_id: str) -> RankedProduct:
    return RankedProduct(
        product_id=product_id,
        title=product_id,
        final_score=0.9,
        relevance_score=0.9,
        rating_score=0.8,
        volume_confidence=1.0,
        avg_rating=4.5,
        review_count=50,
        semantic_score=0.9,
        text="t",
    )


def test_semantic_cache_roundtrip() -> None:
    if not get_settings().openai_api_key or not _reachable(6333):
        pytest.skip("needs OPENAI_API_KEY + Qdrant")
    embeddings = get_dense_embeddings()
    semantic = SemanticCache()
    semantic.ensure_collection()
    version = f"test-{uuid.uuid4().hex[:8]}"
    result = RankingResult(products=[_ranked("A")], no_match=False)

    near_vec = embeddings.embed_query("headphones with good bass")
    semantic.store(near_vec, version, "headphones with good bass", result)

    hit = semantic.lookup(near_vec, version, threshold=0.9)
    assert hit is not None and hit.products[0].product_id == "A"

    far_vec = embeddings.embed_query("how to bake sourdough bread at home")
    assert semantic.lookup(far_vec, version, threshold=0.97) is None  # unrelated -> miss


def test_cached_recommend_response_cache() -> None:
    if not get_settings().openai_api_key or not _reachable(6333) or not _reachable(6379):
        pytest.skip("needs OPENAI_API_KEY + Qdrant + Redis")
    QdrantHybridStore().index(load_catalog())
    clear_version_memo()
    cache = RedisCache(make_redis())
    semantic = SemanticCache()
    semantic.ensure_collection()
    embeddings = get_dense_embeddings()
    store = QdrantHybridStore()

    first = cached_recommend("good bass headphones", store, cache, semantic, embeddings, k=3)
    second = cached_recommend("good bass headphones", store, cache, semantic, embeddings, k=3)
    assert [p.product_id for p in first.products] == [p.product_id for p in second.products]
    assert len(first.products) >= 1
