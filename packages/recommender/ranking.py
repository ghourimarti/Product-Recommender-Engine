"""Rating-aware ranking blend: turns retrieval results into recommendations.

This is the recommender's core. It combines three signals:

    final = relevance_weight * relevance
          + rating_weight   * rating_norm * volume_confidence

- ``relevance``         : the (clamped) hybrid retrieval score — semantic + keyword fit.
- ``rating_norm``       : avg_rating mapped 1->0, 5->1.
- ``volume_confidence`` : review_count / volume_saturation, capped at 1.0 — so a high
                          average from very few reviews can't outweigh a solid average
                          from many. With this dataset (50 reviews each) it's ~1.0, but
                          the formula generalizes to real catalogs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.models import RankedProduct, RankingResult, RetrievedProduct


class RankingConfig(BaseModel):
    """Tunable ranking weights."""

    relevance_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    rating_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    volume_saturation: int = Field(default=50, ge=1)
    min_relevance: float = Field(default=0.05, ge=0.0, le=1.0)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def rank_products(
    candidates: list[RetrievedProduct], config: RankingConfig | None = None
) -> RankingResult:
    """Rank retrieved candidates by the rating-aware blend; flag low-relevance no-match."""
    cfg = config or RankingConfig()
    if not candidates:
        return RankingResult(products=[], no_match=True)

    ranked: list[RankedProduct] = []
    for candidate in candidates:
        relevance = _clamp01(candidate.semantic_score)
        rating_norm = _clamp01((candidate.avg_rating - 1.0) / 4.0)
        volume = min(candidate.review_count / cfg.volume_saturation, 1.0)
        final = cfg.relevance_weight * relevance + cfg.rating_weight * rating_norm * volume
        ranked.append(
            RankedProduct(
                product_id=candidate.product_id,
                title=candidate.title,
                final_score=round(final, 6),
                relevance_score=round(relevance, 6),
                rating_score=round(rating_norm, 6),
                volume_confidence=round(volume, 6),
                avg_rating=candidate.avg_rating,
                review_count=candidate.review_count,
                semantic_score=candidate.semantic_score,
                text=candidate.text,
            )
        )

    # Sort by final score, then avg_rating, then review_count — all higher-is-better.
    ranked.sort(key=lambda r: (r.final_score, r.avg_rating, r.review_count), reverse=True)
    best_relevance = max(_clamp01(c.semantic_score) for c in candidates)
    return RankingResult(products=ranked, no_match=best_relevance < cfg.min_relevance)
