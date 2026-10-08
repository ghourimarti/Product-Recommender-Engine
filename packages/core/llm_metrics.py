"""Prometheus metrics for every LLM call: count, outcome, latency and tokens per provider/model.

Langfuse shows each call; these show the rates. A LangChain callback, so the request code needs
no changes. With the Groq -> OpenAI -> Anthropic fallback chain every attempt is its own call:
a Groq error followed by an OpenAI success shows up as a failover, per provider.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from prometheus_client import Counter, Histogram

logger = logging.getLogger("p2.llm")

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "LLM calls by provider, model and outcome",
    ["provider", "model", "status"],
)
LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "LLM call latency (s), including streamed calls end to end",
    ["provider", "model"],
    buckets=(0.25, 0.5, 1, 2, 4, 8, 16, 32, 64),
)
LLM_TOKENS = Counter(
    "llm_tokens_total", "LLM tokens by provider, model and direction", ["provider", "model", "type"]
)

_CLASS_PROVIDERS = {"ChatGroq": "groq", "ChatOpenAI": "openai", "ChatAnthropic": "anthropic"}


def _labels(serialized: dict[str, Any] | None, kwargs: dict[str, Any]) -> tuple[str, str]:
    """(provider, model): LangChain's ls_* metadata first, then the model's own parameters."""
    metadata = kwargs.get("metadata") or {}
    params = kwargs.get("invocation_params") or {}
    class_name = ((serialized or {}).get("id") or ["unknown"])[-1]
    provider = metadata.get("ls_provider") or _CLASS_PROVIDERS.get(class_name, class_name.lower())
    model = metadata.get("ls_model_name") or params.get("model") or params.get("model_name")
    return str(provider), str(model or "unknown")


def _token_usage(response: LLMResult) -> tuple[int, int]:
    """(input, output) tokens from a chat message's usage_metadata or the provider's llm_output."""
    for generations in response.generations:
        for generation in generations:
            usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if usage:
                return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    output = response.llm_output or {}
    usage = output.get("token_usage") or output.get("usage") or {}
    return (
        int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
    )


class LLMMetricsCallback(BaseCallbackHandler):
    """Records LLM_* metrics. One shared instance is safe across concurrent requests."""

    def __init__(self) -> None:
        self._runs: dict[UUID, tuple[float, str, str]] = {}
        self._lock = threading.Lock()

    def _start(
        self, serialized: dict[str, Any] | None, run_id: UUID, kwargs: dict[str, Any]
    ) -> None:
        provider, model = _labels(serialized, kwargs)
        with self._lock:
            self._runs[run_id] = (time.perf_counter(), provider, model)

    def _finish(self, run_id: UUID) -> tuple[float, str, str] | None:
        with self._lock:
            started = self._runs.pop(run_id, None)
        if started is None:
            return None
        t0, provider, model = started
        LLM_LATENCY.labels(provider, model).observe(time.perf_counter() - t0)
        return t0, provider, model

    def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._start(serialized, run_id, kwargs)

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._start(serialized, run_id, kwargs)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        finished = self._finish(run_id)
        if finished is None:
            return
        _, provider, model = finished
        LLM_REQUESTS.labels(provider, model, "ok").inc()
        tokens_in, tokens_out = _token_usage(response)
        if tokens_in:
            LLM_TOKENS.labels(provider, model, "input").inc(tokens_in)
        if tokens_out:
            LLM_TOKENS.labels(provider, model, "output").inc(tokens_out)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        finished = self._finish(run_id)
        if finished is None:
            return
        _, provider, model = finished
        LLM_REQUESTS.labels(provider, model, "error").inc()
        # The fallback chain swallows this error, so without a log line a dead provider is
        # invisible: users still get answers, from the next (possibly paid) provider.
        logger.warning(
            "LLM call failed provider=%s model=%s error=%s: %s",
            provider,
            model,
            type(error).__name__,
            str(error)[:200],
        )


# One instance for the process: it holds only in-flight start times.
LLM_METRICS_CALLBACK = LLMMetricsCallback()
