"""RAG core interfaces (Decision 6: framework-agnostic seams).

These Protocols are the seams that let us swap the vector store (Astra -> Qdrant in Step 4)
and the retrieval strategy (naive -> hybrid+rerank in Step 6) without touching the web or
service layers. Adapters live under ``app/rag/adapters/``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.schemas.chat import ChatResponse


@dataclass
class RetrievedDoc:
    """A retrieval result, decoupled from any framework's document type."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


@dataclass
class StreamEvent:
    """One SSE event in a streamed answer: token | citations | done | error."""

    event: str
    data: dict[str, Any]


@runtime_checkable
class VectorStoreProvider(Protocol):
    """Owns the embedding + vector store lifecycle for one backend."""

    def get_vectorstore(self) -> Any:
        """Return the backend store object (currently a LangChain VectorStore)."""
        ...

    def add_documents(self, docs: list[Any]) -> None:
        """Ingest documents (embeds + upserts)."""
        ...


@runtime_checkable
class AnswerEngine(Protocol):
    """Produces an answer for a user message within a session."""

    @property
    def ready(self) -> bool: ...

    def answer(self, message: str, session_id: str | None = None) -> ChatResponse: ...

    def astream(self, message: str, session_id: str | None = None) -> AsyncIterator[StreamEvent]:
        """Yield StreamEvents (token/citations/done) for incremental delivery."""
        ...
