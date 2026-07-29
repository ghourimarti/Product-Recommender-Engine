"""PII redaction for logs and prompt-injection defence.

Defence is layered, because no single layer is sufficient:

1. Structural (strongest, already in place). The LLM only authors reasons; the recommended
   product set is fixed by deterministic ranking and merged by ``product_id``. Injected text can
   therefore never add, remove, or reorder a product.
2. Input cleaning (``clean_user_text``). User text is redacted (PII) and injection markers are
   neutralised before it reaches a prompt, which also means before it reaches Langfuse/OTel
   traces, so PII never leaves the process.
3. Prompt delimiting. Untrusted text is wrapped in explicit delimiters and the system prompt
   instructs the model to treat it as data (see ``core.prompts``).
4. Output guardrail (``output_violates_policy``). Even a well-behaved model can be coaxed into
   echoing its instructions, so generated text is checked for system-prompt leakage before it is
   shown to the user. The streaming path checks incrementally and aborts on violation.
"""

from __future__ import annotations

import re

from prometheus_client import Counter

GUARDRAIL_BLOCKS = Counter(
    "guardrail_blocks_total", "Guardrail activations", ["kind"]
)  # kind: input_injection | output_leak

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")

# Phrases an attacker uses to redirect the model. Matched case-insensitively.
_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "ignore the above",
    "ignore your instructions",
    "disregard the above",
    "disregard previous",
    "disregard your instructions",
    "system prompt",
    "you are now",
    "new instructions",
    "forget your instructions",
    "reveal your prompt",
    "print your instructions",
    "act as",
    "pretend to be",
)
_INJECTION_RE = re.compile("|".join(re.escape(m) for m in _INJECTION_MARKERS), re.IGNORECASE)

# Fragments of OUR system prompts. If any appears in generated output, the model is leaking
# its instructions and the response must not be shown.
_SYSTEM_PROMPT_FRAGMENTS = (
    "product-recommendation assistant",
    "shortlist of candidate",
    "grounded only in",
    "do not invent",
    "product_id values exactly",
    "you are a product",
    "system prompt",
    "my instructions are",
    "my system prompt",
)
_LEAK_RE = re.compile("|".join(re.escape(f) for f in _SYSTEM_PROMPT_FRAGMENTS), re.IGNORECASE)

# Minimum characters a streaming caller must withhold for the output guardrail to be sound.
#
# Derivation, so this is a bound rather than a guess. The streaming path appends each token to a
# buffer, re-scans the whole buffer, and releases everything up to `len(buffer) - holdback`. A
# fragment beginning at index `p` is only detected once the buffer reaches `p + L` (L = fragment
# length) -- until the final character arrives there is nothing for the regex to match. The last
# release that can happen *before* detection is therefore at `len(buffer) == p + L - 1`, which
# releases up to `p + L - 1 - holdback`. For the fragment's first character to stay unreleased:
#
#     p + L - 1 - holdback <= p     <=>     holdback >= L - 1
#
# So withholding at least (longest fragment - 1) guarantees no part of a leak can reach the client
# before the leak is detected. This is independent of token size, because the bound is taken over
# the largest buffer length that can precede detection.
#
# Callers should hold back comfortably more than this floor, so that adding a new fragment later
# does not silently invalidate the guarantee. `test_security.py` asserts the invariant holds.
MAX_LEAK_FRAGMENT = max(len(f) for f in _SYSTEM_PROMPT_FRAGMENTS)
MIN_GUARD_HOLDBACK = MAX_LEAK_FRAGMENT - 1

SAFE_EXPLANATION = (
    "Here are your top matches, ranked by how well they fit your request and how well they're "
    "rated. (A detailed explanation wasn't available for this request.)"
)


def redact_pii(text: str) -> str:
    """Redact emails, phone numbers, and card-like number runs."""
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _CARD.sub("[REDACTED_CARD]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    return text


def contains_injection_markers(text: str) -> bool:
    """True if the text contains a known prompt-injection phrase."""
    return _INJECTION_RE.search(text) is not None


def neutralize_injection(text: str) -> str:
    """Defang injection phrases so they read as inert data rather than instructions."""
    return _INJECTION_RE.sub("[filtered]", text)


def clean_user_text(text: str) -> str:
    """Edge sanitiser: redact PII, then neutralise injection phrases.

    Applied once at the API boundary, so the cleaned text is what reaches retrieval, the LLM,
    the trace exporters (Langfuse/OTel) and the chat-history store. PII therefore never leaves
    the process, and injection phrases never reach a prompt.
    """
    if contains_injection_markers(text):
        GUARDRAIL_BLOCKS.labels("input_injection").inc()
    return neutralize_injection(redact_pii(text))


def output_violates_policy(text: str) -> bool:
    """True if generated text leaks system-prompt content (must not be shown to the user)."""
    return _LEAK_RE.search(text) is not None


def guard_output(text: str) -> str:
    """Return the text, or a safe replacement if it leaks system-prompt content."""
    if output_violates_policy(text):
        GUARDRAIL_BLOCKS.labels("output_leak").inc()
        return SAFE_EXPLANATION
    return text
