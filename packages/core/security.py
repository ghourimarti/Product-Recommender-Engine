"""Security helpers (Decision 18): PII redaction for logs + prompt-injection markers.

Note on prompt injection: the strongest defense here is structural, not heuristic — the LLM
only authors *reasons*; the recommended product set is fixed by our deterministic ranking and
merged by product_id (see recommender.chat._merge), so injected text in a review can never add
or swap a product. The system prompts additionally instruct the model to treat reviews as data.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")

_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "ignore the above",
    "disregard the above",
    "disregard previous",
    "system prompt",
    "you are now",
    "new instructions",
)


def redact_pii(text: str) -> str:
    """Redact emails, phone numbers, and card-like number runs (for safe logging)."""
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _CARD.sub("[REDACTED_CARD]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    return text


def contains_injection_markers(text: str) -> bool:
    """Heuristic flag for common prompt-injection phrases (used for logging/guardrails)."""
    lowered = text.lower()
    return any(marker in lowered for marker in _INJECTION_MARKERS)
