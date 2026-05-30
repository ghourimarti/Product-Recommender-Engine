"""Step 11: response + semantic cache behavior, and RagService cache integration."""
from __future__ import annotations

import hashlib

import fakeredis

from app.cache.chat_cache import ChatCache
from app.rag.service import RagService
from app.schemas.chat import ChatResponse


class HashEmbedder:
    def embed_query(self, text: str) -> list[float]:
        d = hashlib.sha256(text.encode()).digest()
        return [d[0] / 255, d[1] / 255, d[2] / 255]


class ConstEmbedder:
    """Same vector for any text -> forces a semantic-cache match."""

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class CountingEngine:
    def __init__(self):
        self.calls = 0

    @property
    def ready(self) -> bool:
        return True

    def answer(self, message: str, session_id: str | None = None) -> ChatResponse:
        self.calls += 1
        return ChatResponse(answer=f"ans:{message}", session_id=session_id or "sid")


def test_exact_response_cache():
    c = ChatCache(fakeredis.FakeRedis(), embedder=HashEmbedder())
    assert c.get("how is the battery") is None
    c.set("how is the battery", ChatResponse(answer="6-8 hours", session_id="s"))
    hit = c.get("how is the battery")
    assert hit is not None and hit.cached and hit.answer == "6-8 hours"


def test_semantic_cache_hit():
    c = ChatCache(fakeredis.FakeRedis(), embedder=ConstEmbedder())
    c.set("battery life?", ChatResponse(answer="6-8 hours", session_id="s"))
    hit = c.get("how long does the charge last")  # different text, same const vec
    assert hit is not None and hit.cached and hit.answer == "6-8 hours"


def test_service_serves_second_call_from_cache():
    engine = CountingEngine()
    svc = RagService(engine=engine, cache=ChatCache(fakeredis.FakeRedis(), embedder=HashEmbedder()))
    r1 = svc.answer("best earbuds?", use_cache=True)   # first-turn standalone -> cacheable
    r2 = svc.answer("best earbuds?", use_cache=True)
    assert engine.calls == 1                            # second call hit cache
    assert r1.cached is False and r2.cached is True


def test_service_bypasses_cache_when_disabled():
    engine = CountingEngine()
    svc = RagService(engine=engine, cache=ChatCache(fakeredis.FakeRedis(), embedder=HashEmbedder()))
    svc.answer("best earbuds?", use_cache=False)        # follow-up turn -> not cached
    svc.answer("best earbuds?", use_cache=False)
    assert engine.calls == 2
