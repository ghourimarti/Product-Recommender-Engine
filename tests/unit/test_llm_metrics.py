"""LLM metrics: every call is counted per provider and model, with latency, tokens and outcome."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableLambda
from prometheus_client import REGISTRY

from core.llm_metrics import LLMMetricsCallback


def _sample(name: str, labels: dict[str, str]) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _model(**metadata: Any) -> GenericFakeChatModel:
    reply = AIMessage(
        content="ok", usage_metadata={"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}
    )
    return GenericFakeChatModel(messages=iter([reply]), metadata=metadata)


class _Broken(GenericFakeChatModel):
    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provider down")


def test_a_successful_call_counts_latency_and_tokens() -> None:
    labels = {"provider": "groq", "model": "test-model-ok"}
    before = _sample("llm_requests_total", {**labels, "status": "ok"})
    tokens_in = _sample("llm_tokens_total", {**labels, "type": "input"})
    tokens_out = _sample("llm_tokens_total", {**labels, "type": "output"})
    observed = _sample("llm_request_duration_seconds_count", labels)

    model = _model(ls_provider="groq", ls_model_name="test-model-ok")
    model.invoke("hi", config={"callbacks": [LLMMetricsCallback()]})

    assert _sample("llm_requests_total", {**labels, "status": "ok"}) == before + 1
    assert _sample("llm_tokens_total", {**labels, "type": "input"}) == tokens_in + 12
    assert _sample("llm_tokens_total", {**labels, "type": "output"}) == tokens_out + 5
    assert _sample("llm_request_duration_seconds_count", labels) == observed + 1


def test_a_failed_attempt_then_a_fallback_shows_both_providers() -> None:
    failing = {"provider": "groq", "model": "down-model", "status": "error"}
    fallback = {"provider": "openai", "model": "backup-model", "status": "ok"}
    errors_before = _sample("llm_requests_total", failing)
    ok_before = _sample("llm_requests_total", fallback)

    broken = _Broken(
        messages=iter([]), metadata={"ls_provider": "groq", "ls_model_name": "down-model"}
    )
    chain = broken.with_fallbacks([_model(ls_provider="openai", ls_model_name="backup-model")])
    chain.invoke("hi", config={"callbacks": [LLMMetricsCallback()]})

    assert _sample("llm_requests_total", failing) == errors_before + 1
    assert _sample("llm_requests_total", fallback) == ok_before + 1


def test_provider_falls_back_to_the_model_class_without_metadata() -> None:
    callback = LLMMetricsCallback()
    serialized = {"id": ["langchain_groq", "chat_models", "ChatGroq"]}
    callback.on_chat_model_start(
        serialized, [[]], run_id=uuid.uuid4(), invocation_params={"model": "m-1"}
    )
    ((_, provider, model),) = callback._runs.values()
    assert (provider, model) == ("groq", "m-1")


def test_an_end_without_a_start_is_ignored() -> None:
    LLMMetricsCallback().on_llm_end(LLMResult(generations=[]), run_id=uuid.uuid4())  # no raise


def test_non_llm_steps_leave_no_runs_behind() -> None:
    callback = LLMMetricsCallback()
    RunnableLambda(lambda x: x).invoke("x", config={"callbacks": [callback]})
    assert callback._runs == {}
