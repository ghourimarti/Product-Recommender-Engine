"""Core package — shared Pydantic schemas, prompts, LLM/embedding clients, chain.

Real logic lands in later transformation steps (Steps 2, 6, 9, 12).
"""

__version__ = "0.1.0"


def healthcheck() -> str:
    """Return a readiness marker; replaced with real logic in later steps."""
    return "core ok"
