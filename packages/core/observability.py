"""Observability wiring: OpenTelemetry traces + Langfuse LLM callbacks.

Everything degrades gracefully:
- No ``otel_exporter_otlp_endpoint`` -> spans are created but not exported (no error).
- No Langfuse keys -> no callback handler (LLM calls still run).
This lets the app run locally with zero observability config, while production just sets env.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from opentelemetry import trace

from core.config import Settings, get_settings

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


def get_langchain_callbacks(settings: Settings | None = None) -> list[Any]:
    """Langfuse callback handler(s) if keys are configured, else an empty list."""
    settings = settings or get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse keys not set; LLM tracing disabled")
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
        # Never break a request over telemetry — but make the failure LOUD, not silent.
        logger.warning("Langfuse callback unavailable; LLM cost/token tracing OFF", exc_info=True)
        return []


def configure_observability(app: Any) -> None:
    """One-call setup for the API: logging, traces, instrumentation."""
    configure_logging()
    try:
        setup_telemetry()
    except Exception:
        logger.warning("OTel tracer setup failed; traces disabled", exc_info=True)
    instrument_fastapi(app)
