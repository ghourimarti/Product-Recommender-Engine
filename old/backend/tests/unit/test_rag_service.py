"""Step 3: RagService delegates to the AnswerEngine abstraction."""
from __future__ import annotations

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.rag.service import RagService
from app.schemas.chat import ChatResponse


class FakeEngine:
    def __init__(self, ready: bool = True):
        self._ready = ready

    @property
    def ready(self) -> bool:
        return self._ready

    def answer(self, message: str, session_id: str | None = None) -> ChatResponse:
        return ChatResponse(answer=f"engine:{message}", session_id=session_id or "sid")


def test_service_delegates_to_engine():
    svc = RagService(engine=FakeEngine(ready=True))
    assert svc.ready is True
    assert svc.answer("hello").answer == "engine:hello"


def test_service_not_ready_without_engine():
    svc = RagService(engine=None)
    assert svc.ready is False
    with pytest.raises(ServiceUnavailableError):
        svc.answer("hello")


def test_service_not_ready_when_engine_not_ready():
    svc = RagService(engine=FakeEngine(ready=False))
    assert svc.ready is False
    with pytest.raises(ServiceUnavailableError):
        svc.answer("hello")
