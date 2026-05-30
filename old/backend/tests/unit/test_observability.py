"""Step 17: cost/token accounting, tracing/langfuse no-op safety."""
from __future__ import annotations

import fakeredis

from app.core.budget import TokenBudget
from app.observability.cost import estimate_tokens, record_usage


def test_estimate_tokens():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 40) == 10


def test_record_usage_consumes_budget_and_returns_cost():
    budget = TokenBudget(fakeredis.FakeRedis())
    cost = record_usage(budget, "user-1", "llama-3.1-8b-instant", prompt_tokens=100, completion_tokens=50)
    assert cost > 0
    assert budget.used("user-1") == 150


def test_record_usage_skips_budget_for_anonymous():
    budget = TokenBudget(fakeredis.FakeRedis())
    record_usage(budget, None, "llama-3.1-8b-instant", 10, 10)  # anonymous -> no consume
    assert budget.used("anonymous") == 0


def test_tracing_noop_when_disabled():
    from app.observability.tracing import configure_tracing

    configure_tracing(object())  # disabled by default -> must not raise


def test_langfuse_none_when_unconfigured():
    from app.observability.langfuse_client import get_langfuse

    assert get_langfuse() is None
