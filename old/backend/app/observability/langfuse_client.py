"""Langfuse client (Decision 13: LLM-specific observability).

Returns a configured client when keys are present, else None (no-op) so the app runs without
Langfuse. In prod, the engine attaches the Langfuse callback handler to trace each
retrieval+generation step with token/cost/latency.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


@lru_cache
def get_langfuse() -> Any | None:
    if not (settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:  # noqa: BLE001
        logger.exception("langfuse_init_failed")
        return None
