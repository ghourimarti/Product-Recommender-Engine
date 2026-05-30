"""Step 16: retry, circuit breaker, cache degradation, engine-failure graceful answer."""
from __future__ import annotations

import pytest

from app.core.resilience import CircuitBreaker, CircuitOpenError, retry


def test_retry_succeeds_after_failures():
    calls = {"n": 0}

    @retry(max_attempts=3, base_delay=0)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_gives_up():
    @retry(max_attempts=2, base_delay=0)
    def always_fail():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        always_fail()


def test_circuit_breaker_opens_and_recovers():
    clock = {"t": 0.0}
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=10, clock=lambda: clock["t"])

    def fail():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(fail)
    assert cb.state == "open"
    with pytest.raises(CircuitOpenError):
        cb.call(fail)

    clock["t"] = 11.0  # past reset timeout
    assert cb.state == "half-open"
    assert cb.call(lambda: "ok") == "ok"  # success closes it
    assert cb.state == "closed"


def test_cache_degrades_when_redis_down():
    from app.cache.chat_cache import ChatCache

    class BrokenRedis:
        def get(self, *a, **k):
            raise ConnectionError("down")

        def setex(self, *a, **k):
            raise ConnectionError("down")

    cache = ChatCache(BrokenRedis(), embedder=None)
    assert cache.get("q") is None  # no crash
    from app.schemas.chat import ChatResponse

    cache.set("q", ChatResponse(answer="a", session_id="s"))  # no crash


def test_service_degrades_on_engine_failure():
    from app.rag.service import RagService

    class FailingEngine:
        ready = True

        def answer(self, message, session_id=None):
            raise RuntimeError("provider exhausted")

    resp = RagService(engine=FailingEngine()).answer("hi")
    assert "trouble" in resp.answer.lower()
    assert resp.cached is False
