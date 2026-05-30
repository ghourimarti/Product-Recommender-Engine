"""Scaffold smoke test: every Python package imports and reports readiness."""

from core import healthcheck as core_health
from evaluation import healthcheck as evaluation_health
from recommender import healthcheck as recommender_health
from retrieval import healthcheck as retrieval_health


def test_packages_load() -> None:
    assert core_health() == "core ok"
    assert retrieval_health() == "retrieval ok"
    assert recommender_health() == "recommender ok"
    assert evaluation_health() == "evaluation ok"
