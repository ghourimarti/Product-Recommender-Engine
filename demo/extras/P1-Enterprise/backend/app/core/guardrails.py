import re
from typing import Tuple

from app.observability.logger import get_logger
from app.observability.metrics import guardrail_violations_total

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt injection patterns
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|context|rules?)",
    r"you\s+are\s+now\s+(?:a\s+)?\w+",
    r"forget\s+(?:everything|all|your\s+instructions?)",
    r"(?:pretend|act|behave)\s+(?:like|as\s+if?)",
    r"disregard\s+(?:your|the|all)\s+(?:instructions?|rules?|guidelines?|training)",
    r"jailbreak",
    r"\bDAN\b",
    r"developer\s+mode",
    r"<\s*system\s*>",
    r"\[\s*(?:system|INST|SYS)\s*\]",
    r"new\s+(?:system\s+)?prompt\s*:",
    r"override\s+(?:your\s+)?(?:instructions?|rules?|guidelines?)",
    r"you\s+(?:must|should|will)\s+(?:now\s+)?(?:ignore|disregard|forget)",
]

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------
_PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+\d{1,3}[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
}

MAX_QUERY_LENGTH = 500
MIN_QUERY_LENGTH = 3

_compiled_injection = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_compiled_pii = {k: re.compile(v) for k, v in _PII_PATTERNS.items()}


def _check_length(text: str) -> Tuple[bool, str]:
    if len(text) < MIN_QUERY_LENGTH:
        guardrail_violations_total.labels(type="too_short").inc()
        return True, "Query is too short. Please describe your anime preferences in more detail."
    if len(text) > MAX_QUERY_LENGTH:
        guardrail_violations_total.labels(type="too_long").inc()
        return True, f"Query exceeds the {MAX_QUERY_LENGTH}-character limit."
    return False, ""


def _check_injection(text: str) -> Tuple[bool, str]:
    for pattern in _compiled_injection:
        if pattern.search(text):
            guardrail_violations_total.labels(type="prompt_injection").inc()
            logger.warning(f"Prompt injection attempt detected pattern={pattern.pattern!r}")
            return True, "Query contains disallowed instructions."
    return False, ""


def _check_pii(text: str) -> Tuple[bool, str]:
    for pii_type, pattern in _compiled_pii.items():
        if pattern.search(text):
            guardrail_violations_total.labels(type=f"pii_{pii_type}").inc()
            logger.warning(f"PII detected in query type={pii_type}")
            return True, f"Query appears to contain personal information ({pii_type}). Please rephrase without personal details."
    return False, ""


def validate_input(query: str) -> Tuple[bool, str]:
    """Return (is_blocked, reason). is_blocked=True means reject the request."""
    for check_fn in (_check_length, _check_injection, _check_pii):
        blocked, reason = check_fn(query)
        if blocked:
            return True, reason
    return False, ""


def validate_output(response: str) -> Tuple[bool, str]:
    """Return (is_valid, message). is_valid=False means the output should not be returned."""
    if not response or not response.strip():
        guardrail_violations_total.labels(type="empty_output").inc()
        return False, "Model returned an empty response."
    if len(response.strip()) < 50:
        guardrail_violations_total.labels(type="output_too_short").inc()
        return False, "Model response was too short to be a valid recommendation."
    return True, response
