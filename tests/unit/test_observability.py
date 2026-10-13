"""Unit tests for observability wiring. Graceful-degradation paths; no network."""

from __future__ import annotations

import uuid
from typing import Any

from opentelemetry import trace

from core.config import Settings
from core.llm_metrics import LLM_METRICS_CALLBACK
from core.observability import get_langchain_callbacks, setup_telemetry, tracer


def test_no_langfuse_keys_means_metrics_only() -> None:
    # Langfuse tracing is off without keys; the Prometheus LLM metrics are always recorded.
    settings = Settings(langfuse_public_key="", langfuse_secret_key="")
    assert get_langchain_callbacks(settings) == [LLM_METRICS_CALLBACK]


def test_setup_telemetry_without_endpoint_is_noop() -> None:
    setup_telemetry(Settings(otel_exporter_otlp_endpoint=""))  # must not raise


def test_tracer_span_is_usable_without_provider() -> None:
    # ProxyTracer works even when no exporter/provider is configured.
    with tracer.start_as_current_span("test-span"):
        pass


# ---- Langfuse v4: typed steps (the trace graph), one trace per run, Jaeger untouched -------


def _traced_chain_run(times: int) -> tuple[list[Any], Any]:
    """Run a tiny prompt -> chat-model chain through P2's Langfuse handler, offline."""
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.prompts import ChatPromptTemplate
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from core import observability

    # A key of its own: the SDK keeps one client per public key, and an earlier test's client
    # is already shut down.
    key = f"pk-lf-test-{uuid.uuid4().hex[:8]}"
    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key=key,
        secret_key="sk-lf-test",
        host="http://127.0.0.1:9",
        tracer_provider=TracerProvider(),
        span_exporter=exporter,
    )
    handler = observability._trace_per_run_handler()(public_key=key)
    chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | GenericFakeChatModel(
        messages=iter([AIMessage(content="ok")] * times)
    )
    for i in range(times):
        chain.invoke({"q": f"question {i}"}, config={"callbacks": [handler]})
    client.flush()
    spans = list(exporter.get_finished_spans())
    client.shutdown()
    return spans, client


def test_langchain_steps_are_typed_so_langfuse_draws_a_graph() -> None:
    spans, _ = _traced_chain_run(1)
    types = {s.attributes.get("langfuse.observation.type") for s in spans}
    # Any type other than span/event/generation makes Langfuse show the agent graph.
    assert "chain" in types and "generation" in types, types


def test_each_top_level_run_is_its_own_trace_even_inside_a_request_span() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    request_span = TracerProvider().get_tracer("fastapi").start_span("POST /chat")
    with trace.use_span(request_span, end_on_exit=True):
        spans, _ = _traced_chain_run(2)
    traces = {s.context.trace_id for s in spans}
    assert len(traces) == 2  # one per run, not both inside the request's trace
    assert request_span.get_span_context().trace_id not in traces
    roots = [s for s in spans if s.attributes.get("langfuse.internal.as_root")]
    assert len(roots) == 2 and {r.context.trace_id for r in roots} == traces


def test_langfuse_leaves_jaegers_global_provider_alone() -> None:
    before = trace.get_tracer_provider()
    _traced_chain_run(1)
    assert trace.get_tracer_provider() is before


def test_configured_host_beats_a_stale_base_url_env(monkeypatch: Any) -> None:
    # .env files keep old keys around; LANGFUSE_BASE_URL must not redirect P2's traces.
    from core import observability

    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:2008")
    key = f"pk-lf-test-{uuid.uuid4().hex[:8]}"
    client = observability._langfuse_client(key, "sk-lf-test", "http://langfuse-web:3000")
    try:
        assert client._base_url == "http://langfuse-web:3000"
    finally:
        client.shutdown()
