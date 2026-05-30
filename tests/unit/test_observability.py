"""Unit tests for observability wiring (Step 11). Graceful-degradation paths; no network."""

from __future__ import annotations

from core.config import Settings
from core.observability import get_langchain_callbacks, setup_telemetry, tracer


def test_no_langfuse_keys_means_no_callbacks() -> None:
    settings = Settings(langfuse_public_key="", langfuse_secret_key="")
    assert get_langchain_callbacks(settings) == []


def test_setup_telemetry_without_endpoint_is_noop() -> None:
    setup_telemetry(Settings(otel_exporter_otlp_endpoint=""))  # must not raise


def test_tracer_span_is_usable_without_provider() -> None:
    # ProxyTracer works even when no exporter/provider is configured.
    with tracer.start_as_current_span("test-span"):
        pass
