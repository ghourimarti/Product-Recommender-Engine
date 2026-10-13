"""Observability wiring: OpenTelemetry traces + Langfuse LLM callbacks.

Everything degrades gracefully:
- No ``otel_exporter_otlp_endpoint`` -> spans are created but not exported (no error).
- No Langfuse keys -> no callback handler (LLM calls still run).
This lets the app run locally with zero observability config, while production just sets env.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from typing import Any

from opentelemetry import trace

from core.config import Settings, get_settings
from core.llm_metrics import LLM_METRICS_CALLBACK

logger = logging.getLogger("p2.observability")

# A ProxyTracer; it picks up the real provider once setup_telemetry installs one.
tracer = trace.get_tracer("p2-recommender")


def configure_logging(settings: Settings | None = None) -> None:
    """Install app logging honouring LOG_LEVEL.

    Without this, the root logger defaults to WARNING and every ``logger.info(...)`` in the
    app — including the PII-redacted request lines — is silently dropped, leaving the service
    with no application-level logs at all.
    """
    settings = settings or get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    if not any(getattr(h, "_p2", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler._p2 = True  # type: ignore[attr-defined]  # marker: don't double-install
        root.addHandler(handler)
    logging.getLogger("p2").setLevel(level)


def setup_telemetry(settings: Settings | None = None) -> None:
    """Install an OTLP-exporting tracer provider if an endpoint is configured."""
    settings = settings or get_settings()
    if not settings.otel_exporter_otlp_endpoint:
        return
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        )
    )
    trace.set_tracer_provider(provider)


def instrument_fastapi(app: Any) -> None:
    try:  # instrumentation is best-effort; never break the app — but never fail SILENTLY either
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        logger.warning("FastAPI OTel instrumentation failed; traces degraded", exc_info=True)


@lru_cache(maxsize=4)
def _langfuse_client(public_key: str, secret_key: str, host: str) -> Any:
    """One Langfuse client per key set, on its own OpenTelemetry tracer provider.

    The SDK (v4) is built on OpenTelemetry and otherwise joins the global provider, which is
    Jaeger's (setup_telemetry). Jaeger would then receive every LLM step, prompts and
    completions included, and whichever of the two started first would own the global
    provider. A private provider keeps the two pipelines apart: Jaeger is unchanged.
    """
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider

    # base_url, not host: the SDK lets a LANGFUSE_BASE_URL environment variable outrank `host`,
    # and a stale one (a host URL inside the container) silently sends every trace nowhere.
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=host,
        tracer_provider=TracerProvider(),
    )


@lru_cache(maxsize=1)
def _trace_per_run_handler() -> type:
    """Langfuse's LangChain handler, starting one trace per top-level LangChain run.

    v4 types every LangChain step (chain, generation, tool, ...), which is what makes Langfuse
    draw a trace as a graph. Unlike v2 it starts a top-level run inside the active
    OpenTelemetry span (here the FastAPI request span), which would merge every LLM call of a
    request into one trace. A fresh trace id per top-level run keeps one trace per run, as v2
    did. The hook is private SDK API: tests/unit/test_observability.py fails if it moves.
    """
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    from langfuse.types import TraceContext

    class TracePerRunHandler(CallbackHandler):
        def _take_root_trace_context(
            self, *, inputs: Any, metadata: Any
        ) -> tuple[str | None, TraceContext | None]:
            return None, TraceContext(trace_id=Langfuse.create_trace_id())

    return TracePerRunHandler


def get_langchain_callbacks(settings: Settings | None = None) -> list[Any]:
    """LLM callbacks: Prometheus metrics always, plus Langfuse tracing when its keys are set."""
    settings = settings or get_settings()
    callbacks: list[Any] = [LLM_METRICS_CALLBACK]
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse keys not set; LLM tracing disabled (metrics still recorded)")
        return callbacks
    try:
        _langfuse_client(
            settings.langfuse_public_key,
            settings.langfuse_secret_key,
            settings.langfuse_host or "https://cloud.langfuse.com",
        )
        callbacks.append(_trace_per_run_handler()(public_key=settings.langfuse_public_key))
    except Exception:
        # Never break a request over telemetry — but make the failure LOUD, not silent.
        logger.warning("Langfuse callback unavailable; LLM cost/token tracing OFF", exc_info=True)
    return callbacks


def configure_observability(app: Any) -> None:
    """One-call setup for the API: logging, traces, instrumentation."""
    configure_logging()
    try:
        setup_telemetry()
    except Exception:
        logger.warning("OTel tracer setup failed; traces disabled", exc_info=True)
    instrument_fastapi(app)
