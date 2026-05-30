"""Per-user daily token budget (Decision 20).

Daily Redis counter per user. ``budget_guard`` rejects new work once the budget is spent;
``consume`` is called after a response with the actual token usage (wired to real usage in
Step 17 observability). Anonymous callers are governed by rate limiting, not token budget.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import Depends

from app.api.deps import get_budget
from app.core.config import settings
from app.core.exceptions import BudgetExceededError
from app.core.security import Principal, get_current_user

_DAY_TTL = 86_400


class TokenBudget:
    def __init__(self, redis: Any) -> None:
        self._r = redis

    def _key(self, sub: str) -> str:
        return f"budget:{sub}:{date.today().isoformat()}"

    def used(self, sub: str) -> int:
        return int(self._r.get(self._key(sub)) or 0)

    def over(self, sub: str, limit: int) -> bool:
        return self.used(sub) >= limit

    def consume(self, sub: str, tokens: int) -> int:
        key = self._key(sub)
        total = int(self._r.incrby(key, tokens))
        if total == tokens:
            self._r.expire(key, _DAY_TTL)
        return total


async def budget_guard(
    user: Principal = Depends(get_current_user),
    budget: TokenBudget = Depends(get_budget),
) -> None:
    if not settings.budget_enabled or user.anonymous:
        return
    if budget.over(user.sub, settings.daily_token_budget):
        raise BudgetExceededError("Daily token budget exceeded")
