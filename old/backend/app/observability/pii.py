"""PII scrubbing for logs (Decision 18).

Redacts the most common PII before it reaches log sinks. Applied in the JSON log formatter,
so no log line carries raw emails/phones/cards even if a developer logs a payload.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_PHONE = re.compile(r"\b\+?\d[\d ()-]{7,}\d\b")


def scrub(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = _EMAIL.sub("[EMAIL]", text)
    text = _CARD.sub("[CARD]", text)   # before phone: card digits would also match phone
    text = _PHONE.sub("[PHONE]", text)
    return text
