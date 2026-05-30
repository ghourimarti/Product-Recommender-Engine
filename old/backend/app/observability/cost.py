"""Token + cost tracking (Decision 17/20).

Records token usage and approximate USD cost to Prometheus and consumes the user's daily
token budget (closing the Step-13 TODO). Token counts come from the LLM response metadata in
production; when unavailable we estimate from text length (~4 chars/token).
"""
from __future__ import annotations

from typing import Any

from app.observability.logger import get_logger
from app.observability.metrics import LLM_COST_USD, LLM_TOKENS

logger = get_logger(__name__)

# Approx USD per 1K tokens (input, output). Update as provider pricing changes.
PRICING: dict[str, tuple[float, float]] = {
    "llama-3.1-8b-instant": (0.00005, 0.00008),
    "llama-3.3-70b-versatile": (0.00059, 0.00079),
    "gpt-4o-mini": (0.00015, 0.00060),
    "default": (0.0001, 0.0003),
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def record_usage(
    budget: Any | None,
    user_sub: str | None,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    LLM_TOKENS.labels(model, "prompt").inc(prompt_tokens)
    LLM_TOKENS.labels(model, "completion").inc(completion_tokens)
    p_in, p_out = PRICING.get(model, PRICING["default"])
    cost = (prompt_tokens / 1000 * p_in) + (completion_tokens / 1000 * p_out)
    LLM_COST_USD.labels(model).inc(cost)
    if budget is not None and user_sub:
        try:
            budget.consume(user_sub, prompt_tokens + completion_tokens)
        except Exception:  # noqa: BLE001 - never fail a request on accounting
            logger.warning("budget_consume_failed")
    return cost
