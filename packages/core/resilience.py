"""A minimal circuit breaker (Decision 21).

After ``fail_max`` consecutive failures the breaker opens and callers skip the failing
dependency (serving a degraded path) until ``reset_timeout`` elapses, when one trial call is
allowed (half-open). A success closes it again.
"""

from __future__ import annotations

import time


class CircuitBreaker:
    def __init__(self, fail_max: int = 5, reset_timeout: float = 60.0) -> None:
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        # open until reset_timeout elapses; after that, half-open (allow a trial call)
        return time.monotonic() - self._opened_at < self.reset_timeout

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_max:
            self._opened_at = time.monotonic()
