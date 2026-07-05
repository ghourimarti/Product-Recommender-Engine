"""LLM chain pieces (Decision 4 + 6): provider fallback chain, query rewrite, grounded explain.

All LangChain/provider calls are confined here behind typed functions. The provider chain is
assembled from whichever API keys are configured, in priority order Groq -> OpenAI -> Anthropic
(Decision 4), so the app runs on any single key and auto-prioritizes when more are added.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from core.config import Settings, get_settings
from core.models import ExplanationSet, RankedOffer, RankedProduct
from core.prompts import (
    EXPLAIN_HUMAN,
    EXPLAIN_OFFERS_HUMAN,
    EXPLAIN_OFFERS_SYSTEM,
    EXPLAIN_STREAM_SYSTEM,
    EXPLAIN_SYSTEM,
    REWRITE_SYSTEM,
)

MAX_REVIEW_CHARS = 800  # cap evidence text per product to bound prompt cost


def available_providers(settings: Settings) -> list[str]:
    """LLM providers that have a key configured, in Decision-4 priority order."""
    providers: list[str] = []
    if settings.groq_api_key:
        providers.append("groq")
    if settings.openai_api_key:
        providers.append("openai")
    if settings.anthropic_api_key:
        providers.append("anthropic")
    return providers


def _make_model(provider: str, settings: Settings) -> Any:
    # Any-typed factory map: provider constructors differ across versions; route through
    # Any so runtime kwargs (model=, api_key=) stay correct without fighting each stub.
    factories: dict[str, Any] = {"groq": ChatGroq, "openai": ChatOpenAI, "anthropic": ChatAnthropic}
    model_names = {
        "groq": settings.groq_model,
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
    }
    api_keys = {
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
    }
    if provider not in factories:
        raise ValueError(f"unknown provider: {provider}")
    return factories[provider](
        model=model_names[provider],
        api_key=SecretStr(api_keys[provider]),
        temperature=0.3,
        max_tokens=settings.max_output_tokens,  # per-request cost cap (Decision 20)
    )


def build_chat_model(settings: Settings | None = None) -> Any:
    """Primary chat model with the remaining providers attached as fallbacks (Decision 4)."""
    settings = settings or get_settings()
    providers = available_providers(settings)
    if not providers:
        raise RuntimeError(
            "No LLM provider key configured "
            "(set GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY in .env)."
        )
    models = [_make_model(p, settings) for p in providers]
    primary, *fallbacks = models
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


def _format_products(products: list[RankedProduct]) -> str:
    blocks: list[str] = []
    for p in products:
        blocks.append(
            f"- product_id: {p.product_id}\n"
            f"  title: {p.title}\n"
            f"  avg_rating: {p.avg_rating}\n"
            f"  reviews: {p.text[:MAX_REVIEW_CHARS]}"
        )
    return "\n".join(blocks)


def rewrite_query(
    query: str, history: list[BaseMessage], model: Any, callbacks: list[Any] | None = None
) -> str:
    """History-aware rewrite of the latest message into a standalone query."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", REWRITE_SYSTEM), MessagesPlaceholder("history"), ("human", "{query}")]
    )
    chain = prompt | model | StrOutputParser()
    config = {"callbacks": callbacks or []}
    return str(chain.invoke({"query": query, "history": history}, config=config)).strip()


def explain(
    query: str, products: list[RankedProduct], model: Any, callbacks: list[Any] | None = None
) -> ExplanationSet:
    """Grounded, structured per-product explanations (LLM cannot alter product facts)."""
    structured = model.with_structured_output(ExplanationSet)
    prompt = ChatPromptTemplate.from_messages(
        [("system", EXPLAIN_SYSTEM), ("human", EXPLAIN_HUMAN)]
    )
    chain = prompt | structured
    config = {"callbacks": callbacks or []}
    result: ExplanationSet = chain.invoke(
        {"query": query, "products": _format_products(products)}, config=config
    )
    return result


def _format_offers(offers: list[RankedOffer]) -> str:
    blocks: list[str] = []
    for ranked in offers:
        o = ranked.offer
        price = f"${o.price:.2f}" if o.price is not None else "n/a"
        rating = f"{o.rating} stars from {o.review_count} reviews" if o.rating else "no rating"
        blocks.append(
            f"- product_id: {o.product_id}\n"
            f"  title: {o.title}\n"
            f"  price: {price}\n"
            f"  store: {o.store}\n"
            f"  rating: {rating}\n"
            f"  details: {o.snippet[:300]}"
        )
    return "\n".join(blocks)


def explain_offers(
    query: str, offers: list[RankedOffer], model: Any, callbacks: list[Any] | None = None
) -> ExplanationSet:
    """Grounded per-offer reasons over live shopping offers (aggregator path)."""
    structured = model.with_structured_output(ExplanationSet)
    prompt = ChatPromptTemplate.from_messages(
        [("system", EXPLAIN_OFFERS_SYSTEM), ("human", EXPLAIN_OFFERS_HUMAN)]
    )
    chain = prompt | structured
    config = {"callbacks": callbacks or []}
    result: ExplanationSet = chain.invoke(
        {"query": query, "offers": _format_offers(offers)}, config=config
    )
    return result


async def astream_explanation(
    query: str,
    products: list[RankedProduct],
    model: Any,
    callbacks: list[Any] | None = None,
) -> AsyncIterator[str]:
    """Stream a grounded prose explanation token-by-token (for the SSE /chat path)."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", EXPLAIN_STREAM_SYSTEM), ("human", EXPLAIN_HUMAN)]
    )
    chain = prompt | model | StrOutputParser()
    config = {"callbacks": callbacks or []}
    async for chunk in chain.astream(
        {"query": query, "products": _format_products(products)}, config=config
    ):
        yield str(chunk)
