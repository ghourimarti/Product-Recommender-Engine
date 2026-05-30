"""Guardrails (Decision 18).

The dominant threat for THIS app is prompt-injection via product reviews: reviews are
untrusted user-generated content that flows into the LLM context, so a malicious review
("ignore previous instructions...") could try to hijack the model. Defenses, layered:

  1. neutralize_injection() — strip instruction-injection patterns from review text at
     ingestion (so the stored/retrieved content is data, not commands).
  2. system-prompt hardening (in rag_chain) — tells the model CONTEXT is untrusted data.
  3. check_user_input() — reject control characters / malformed input.

Output moderation is a hook (moderate_output) kept minimal; a model-based classifier
(Llama Guard) is the production upgrade noted in the build-spec.
"""
from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all )?(the )?(previous|prior|above) (instructions|prompts?|messages?)",
        r"disregard (the )?(above|previous|all|system)",
        r"forget (the )?(above|previous|everything)",
        r"you are now\b",
        r"system prompt",
        r"reveal (your|the) (system )?(prompt|instructions)",
        r"\bact as\b (an?|the)\b",
        r"new instructions:",
    )
]
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def detect_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def neutralize_injection(text: str) -> str:
    """Replace instruction-injection phrases in untrusted content with a marker."""
    out = text
    for pattern in _INJECTION_PATTERNS:
        out = pattern.sub("[redacted-instruction]", out)
    return out


def check_user_input(text: str) -> str:
    from app.core.exceptions import BadRequestError

    if _CONTROL_CHARS.search(text):
        raise BadRequestError("Input contains invalid control characters")
    return text


def moderate_output(text: str) -> str:
    """Output filter hook. Minimal today; Llama Guard / moderation API is the upgrade."""
    return text
