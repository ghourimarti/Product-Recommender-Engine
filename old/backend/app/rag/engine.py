"""LangChain-backed AnswerEngine adapter.

Wraps the history-aware retrieval chain behind the AnswerEngine interface. Step 15: builds
one chain per model tier (cheap/strong) sharing the retriever, and routes each query to a
tier via llm_router.select_tier (kill-switch forces cheap).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger
from app.rag.interfaces import StreamEvent, VectorStoreProvider
from app.schemas.chat import Citation, ChatResponse

logger = get_logger(__name__)


class LangChainAnswerEngine:
    def __init__(self, provider: VectorStoreProvider) -> None:
        self._provider = provider
        self._chains: dict[str, Any] | None = None

    @property
    def ready(self) -> bool:
        return self._chains is not None

    def build(self) -> None:
        from app.rag.llm_router import build_tier_model
        from app.rag.rag_chain import RAGChainBuilder
        from app.rag.retriever import build_retriever

        retriever = build_retriever(self._provider.get_vectorstore())
        self._chains = {
            tier: RAGChainBuilder(retriever, build_tier_model(tier)).build_chain()
            for tier in ("cheap", "strong")
        }
        logger.info("answer_engine_built", extra={"tiers": list(self._chains)})

    def _chain_for(self, message: str) -> Any:
        from app.rag.llm_router import select_tier

        tier = select_tier(message, settings.kill_switch)
        logger.info("tier_selected", extra={"tier": tier})
        return self._chains[tier]

    def answer(self, message: str, session_id: str | None = None) -> ChatResponse:
        sid = session_id or str(uuid.uuid4())
        result = self._chain_for(message).invoke(
            {"input": message}, config={"configurable": {"session_id": sid}}
        )
        citations = [
            Citation(product_name=d.metadata.get("product_name", "unknown"), snippet=d.page_content[:200])
            for d in result.get("context", [])
        ]
        return ChatResponse(answer=result["answer"], citations=citations, session_id=sid)

    async def astream(self, message: str, session_id: str | None = None) -> AsyncIterator[StreamEvent]:
        sid = session_id or str(uuid.uuid4())
        emitted_citations = False
        async for chunk in self._chain_for(message).astream(
            {"input": message}, config={"configurable": {"session_id": sid}}
        ):
            if not emitted_citations and chunk.get("context"):
                emitted_citations = True
                yield StreamEvent("citations", {
                    "items": [
                        {"product_name": d.metadata.get("product_name", "unknown"),
                         "snippet": d.page_content[:200]}
                        for d in chunk["context"]
                    ]
                })
            if chunk.get("answer"):
                yield StreamEvent("token", {"text": chunk["answer"]})
        yield StreamEvent("done", {"session_id": sid})
