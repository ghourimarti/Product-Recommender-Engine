"""Observability wiring (Decision 13): OpenTelemetry traces + Langfuse LLM callbacks.

Everything degrades gracefully:
- No ``otel_exporter_otlp_endpoint`` -> spans are created but not exported (no error).
- No Langfuse keys -> no callback handler (LLM calls still run).
This lets the app run locally with zero observability config, while production just sets env.
"""

from __future__ import annotations

import contextlib
from typing import Any

from opentelemetry import trace

from core.config import Settings, get_settings

# A ProxyTracer; it picks up the real provider once setup_telemetry installs one.
tracer = trace.get_tracer("p2-recommender")


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
    with contextlib.suppress(Exception):  # instrumentation is best-effort; never break the app
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)


def get_langchain_callbacks(settings: Settings | None = None) -> list[Any]:
    """Langfuse callback handler(s) if keys are configured, else an empty list."""
    settings = settings or get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return []
    try:
        from langfuse.callback import CallbackHandler

        return [
            CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host or "https://cloud.langfuse.com",
            )
        ]
    except Exception:
        return []


def configure_observability(app: Any) -> None:
    """One-call setup for the API (best-effort)."""
    with contextlib.suppress(Exception):
        setup_telemetry()
        instrument_fastapi(app)
