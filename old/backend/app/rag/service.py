"""RagService: thin facade the API depends on.

Now wraps an injected ``AnswerEngine`` (Step 3) rather than building a LangChain chain
directly — so the web layer is decoupled from both the framework and the vector backend.
``build()`` constructs the engine via the factory; tests inject a fake engine instead.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.exceptions import ServiceUnavailableError
from app.observability.logger import get_logger
from app.rag.interfaces import AnswerEngine, StreamEvent
from app.schemas.chat import ChatResponse

logger = get_logger(__name__)

_DEGRADED_MESSAGE = (
    "I'm having trouble answering right now. Please try again in a moment."
)


class RagService:
    def __init__(self, engine: AnswerEngine | None = None, cache: object | None = None) -> None:
        self._engine = engine
        self._cache = cache

    @property
    def ready(self) -> bool:
        return self._engine is not None and self._engine.ready

    def build(self) -> None:
        from app.rag.factory import build_answer_engine, build_chat_cache

        self._engine = build_answer_engine()
        self._cache = build_chat_cache()
        logger.info("rag_service_built")

    def answer(self, message: str, session_id: str | None = None, use_cache: bool = False) -> ChatResponse:
        if not self.ready:
            raise ServiceUnavailableError("RAG service is not ready")

        # The caller (route) decides cacheability explicitly: only first-turn standalone
        # questions are cached, because history-aware answers are session-specific and must
        # not be cross-served (see ChatCache docstring). Caller, not session presence,
        # controls this — sessions are always scoped per-user upstream.
        cacheable = self._cache is not None and use_cache
        if cacheable:
            hit = self._cache.get(message)
            if hit is not None:
                return hit.model_copy(update={"session_id": session_id or hit.session_id})

        # Degrade, don't fail (D21): if the engine/provider chain is exhausted, return a
        # graceful message rather than a 500. (Provider-level fallback is handled in D4.)
        try:
            response = self._engine.answer(message, session_id)
        except Exception:  # noqa: BLE001
            logger.exception("engine_failed_degrading")
            return ChatResponse(answer=_DEGRADED_MESSAGE, citations=[], session_id=session_id or "")

        if cacheable:
            self._cache.set(message, response)
        return response

    async def astream(self, message: str, session_id: str | None = None) -> AsyncIterator[StreamEvent]:
        if not self.ready:
            raise ServiceUnavailableError("RAG service is not ready")
        async for event in self._engine.astream(message, session_id):
            yield event
