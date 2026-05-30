"""OpenTelemetry tracing setup (Decision 13).

Guarded: if OTel libraries aren't installed or no exporter endpoint is configured, this is a
safe no-op so the app runs everywhere (incl. the keyless test env). In prod it exports OTLP
traces to the collector behind the Grafana/Tempo stack.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


def configure_tracing(app: Any) -> None:
    if not settings.otel_enabled or not settings.otel_exporter_otlp_endpoint:
        logger.info("tracing_disabled")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "product-recommender"}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("tracing_enabled")
    except Exception:  # noqa: BLE001 - never let observability setup break boot
        logger.exception("tracing_setup_failed")
