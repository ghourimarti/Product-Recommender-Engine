"""Evaluation package: ranking metrics and answer-quality harness.

Named ``evaluation`` (not ``eval``) to avoid shadowing the Python builtin.
"""

__version__ = "0.1.0"


def healthcheck() -> str:
    """Return a readiness marker; replaced with real logic in later steps."""
    return "evaluation ok"
