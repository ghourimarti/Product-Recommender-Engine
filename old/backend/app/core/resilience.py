"""Resilience primitives (Decision 21): retry, circuit breaker, timeout.

The guiding principle is *degrade, don't fail*: every external call gets a timeout + retry,
and repeatedly-failing dependencies are short-circuited so one sick dependency doesn't take
the whole service down.
"""
from __future__ import annotations

import functools
import random
import time
from collections.abc import Callable
from typing import Any


def retry(max_attempts: int = 3, base_delay: float = 0.2, exc: tuple[type[Exception], ...] = (Exception,)):
    """Retry with exponential backoff + jitter."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    # Jitter is non-security (just spreads retries); stdlib random is fine.
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, base_delay)  # nosec B311
                    if delay:
                        time.sleep(delay)

        return wrapper

    return decorator


class CircuitOpenError(Exception):
    """Raised when the circuit is open and the call is short-circuited."""


class CircuitBreaker:
    """Closed -> (failures >= threshold) -> Open -> (after reset_timeout) -> Half-open -> Closed."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._threshold = failure_threshold
        self._reset = reset_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self._clock() - self._opened_at >= self._reset:
            return "half-open"
        return "open"

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.state == "open":
            raise CircuitOpenError("circuit open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = self._clock()
            raise
        self._failures = 0
        self._opened_at = None
        return result
