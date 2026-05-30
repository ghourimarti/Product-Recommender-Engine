import time
from typing import Iterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_groq import ChatGroq

from app.core.config import get_settings
from app.observability.logger import get_logger
from app.observability.metrics import rag_requests_total, rag_retrieval_duration_seconds
from app.rag.prompt import ANIME_HUMAN_PROMPT, ANIME_SYSTEM_PROMPT
from app.rag.vector_store import get_retriever

settings = get_settings()
logger = get_logger(__name__)

_chain = None


def _build_chain():
    retriever = get_retriever()

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ANIME_SYSTEM_PROMPT),
            ("human", ANIME_HUMAN_PROMPT),
        ]
    )

    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.MODEL_NAME,
        temperature=0,
        streaming=True,
    )

    def retrieve_with_timing(query: str) -> str:
        start = time.perf_counter()
        docs = retriever.invoke(query)
        elapsed = time.perf_counter() - start
        rag_retrieval_duration_seconds.observe(elapsed)
        logger.info(f"Retrieved {len(docs)} docs in {elapsed:.3f}s")
        return "\n\n".join(doc.page_content for doc in docs)

    # LCEL chain — replaces deprecated RetrievalQA
    chain = (
        {"context": retrieve_with_timing, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain


def get_chain():
    global _chain
    if _chain is None:
        _chain = _build_chain()
    return _chain


def stream_recommendation(query: str) -> Iterator[str]:
    """Stream recommendation chunks. Raises on LLM/retrieval errors."""
    rag_requests_total.labels(status="started").inc()
    try:
        for chunk in get_chain().stream(query):
            yield chunk
        rag_requests_total.labels(status="success").inc()
    except Exception as exc:
        rag_requests_total.labels(status="error").inc()
        logger.error(f"RAG pipeline error: {exc}")
        raise
