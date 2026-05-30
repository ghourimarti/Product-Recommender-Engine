"""LLM tiering + provider fallback (Decision 4).

- Tiering: cheap default model; escalate to a stronger model for complex/comparative queries.
  The kill-switch forces the cheap tier (cost control under pressure).
- Fallback: each tier's primary model is wrapped with a cross-provider fallback so a single
  provider outage doesn't break the SLO.

Decision logic (select_tier / should_escalate) is pure and unit-tested; model construction is
lazy (needs provider SDKs + keys) and verified in a 3.12 venv.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Literal

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)

Tier = Literal["cheap", "strong"]
_COMPARATIVE = re.compile(r"\b(vs|versus|compare|comparison|difference|better than|best|which)\b", re.I)


def should_escalate(query: str) -> bool:
    """Escalate long or comparative questions where the cheap model tends to underperform."""
    words = len(query.split())
    return words > settings.escalate_word_threshold or bool(_COMPARATIVE.search(query))


def select_tier(query: str, kill_switch: bool) -> Tier:
    if kill_switch:
        return "cheap"  # cost control: never escalate under load shedding
    return "strong" if should_escalate(query) else "cheap"


def build_chat_model(model_name: str, provider: str = "groq") -> Any:
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model_name, temperature=settings.rag_temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, temperature=settings.rag_temperature)
    raise ValueError(f"Unknown provider: {provider}")


def build_tier_model(tier: Tier, model_builder: Callable[..., Any] = build_chat_model) -> Any:
    """Build the model for a tier, wrapped with a cross-provider fallback (D4)."""
    name = settings.rag_model_strong if tier == "strong" else settings.rag_model
    primary = model_builder(name, provider="groq")
    if settings.fallback_provider == "none":
        return primary
    fallback = model_builder(settings.fallback_model, provider=settings.fallback_provider)
    return primary.with_fallbacks([fallback])
