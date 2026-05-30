"""Shared test fixtures.

The app is built WITHOUT running the real lifespan (which would import LangChain and need
keys). We attach a fake RagService and override the dependency, so the web layer is tested
in isolation — the value of having extracted RagService in Step 2.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_service
from app.main import create_app
from app.schemas.chat import ChatResponse


class FakeRagService:
    def __init__(self, ready: bool = True):
        self._ready = ready

    @property
    def ready(self) -> bool:
        return self._ready

    def answer(self, message: str, session_id: str | None = None, use_cache: bool = False) -> ChatResponse:
        if not self._ready:
            from app.core.exceptions import ServiceUnavailableError

            raise ServiceUnavailableError("RAG service is not ready")
        return ChatResponse(answer=f"echo: {message}", citations=[], session_id=session_id or "test-sid")

    async def astream(self, message: str, session_id: str | None = None):
        from app.core.exceptions import ServiceUnavailableError
        from app.rag.interfaces import StreamEvent

        if not self._ready:
            raise ServiceUnavailableError("RAG service is not ready")
        sid = session_id or "test-sid"
        yield StreamEvent("citations", {"items": [{"product_name": "X", "snippet": "s"}]})
        for tok in ("echo", ":", message):
            yield StreamEvent("token", {"text": tok})
        yield StreamEvent("done", {"session_id": sid})


def _client(rag: FakeRagService) -> TestClient:
    import fakeredis

    from app.api.deps import get_budget, get_limiter
    from app.core.budget import TokenBudget
    from app.core.rate_limiter import RateLimiter
    from app.core.security import Principal, get_current_user

    app = create_app()
    app.state.rag_service = rag
    app.dependency_overrides[get_rag_service] = lambda: rag
    # Auth is exercised in test_auth.py; route tests run as a fixed test principal.
    app.dependency_overrides[get_current_user] = lambda: Principal(sub="test-user")
    # Rate limiter / budget backed by fakeredis so route tests are hermetic (no real Redis).
    shared = fakeredis.FakeRedis()
    app.dependency_overrides[get_limiter] = lambda: RateLimiter(shared)
    app.dependency_overrides[get_budget] = lambda: TokenBudget(shared)
    # raise_server_exceptions=False so our exception handlers (not pytest) handle errors
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client() -> TestClient:
    return _client(FakeRagService(ready=True))


@pytest.fixture
def client_not_ready() -> TestClient:
    return _client(FakeRagService(ready=False))
