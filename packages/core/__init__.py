"""Core package: shared Pydantic schemas, prompts, and LLM/embedding clients."""

__version__ = "0.1.0"


def healthcheck() -> str:
    """Return a readiness marker."""
    return "core ok"
