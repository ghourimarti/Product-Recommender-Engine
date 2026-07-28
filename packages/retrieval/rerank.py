"""Cross-encoder reranker: re-scores retrieved candidates by query relevance.

Runs locally via fastembed (no API key). A cross-encoder reads the (query, product_text)
pair jointly, which discriminates better than the bi-encoder/RRF retrieval score —
especially for subjective queries. All fastembed calls are confined here so the rest of
the codebase stays strictly typed. The reranker score (sigmoid of the logit) overwrites
``semantic_score``, becoming the relevance signal the ranking blend consumes.
"""

from __future__ import annotations

import math
from typing import Protocol

from fastembed.rerank.cross_encoder import TextCrossEncoder

from core.config import get_settings
from core.models import RetrievedProduct


class Reranker(Protocol):
    """Contract the recommender depends on; concrete impl is swappable."""

    def rerank(self, query: str, candidates: list[RetrievedProduct]) -> list[RetrievedProduct]: ...


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _apply_scores(
    candidates: list[RetrievedProduct], logits: list[float]
) -> list[RetrievedProduct]:
    """Map cross-encoder logits -> [0,1] relevance, overwrite semantic_score, sort desc."""
    rescored = [
        candidate.model_copy(update={"semantic_score": _sigmoid(logit)})
        for candidate, logit in zip(candidates, logits, strict=True)
    ]
    rescored.sort(key=lambda c: c.semantic_score, reverse=True)
    return rescored


class CrossEncoderReranker:
    """bge-reranker (or configured) cross-encoder over candidate product text."""

    def __init__(self) -> None:
        self._model = TextCrossEncoder(model_name=get_settings().reranker_model)

    def rerank(self, query: str, candidates: list[RetrievedProduct]) -> list[RetrievedProduct]:
        if not candidates:
            return []
        logits = [float(s) for s in self._model.rerank(query, [c.text for c in candidates])]
        return _apply_scores(candidates, logits)
