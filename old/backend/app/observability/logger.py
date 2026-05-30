"""Structured JSON logging.

Replaces the demo's file-only ``utils/logger.py``. Logs to stdout as JSON so a container
platform (Docker/K8s) and the OTel/Loki pipeline (Step 17) can ingest them. PII scrubbing
is layered on in Step 14.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from app.observability.pii import scrub

        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": scrub(record.getMessage()),  # PII never reaches the log sink (D18)
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("request_id", "session_id", "latency_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
