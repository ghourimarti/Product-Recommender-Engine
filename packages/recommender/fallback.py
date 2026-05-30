"""Popularity-only ranking — the degraded path when retrieval is unavailable (Decision 21).

No semantic relevance: rank the whole catalog by avg_rating x review-volume confidence.
Used when Qdrant/embeddings are down or the retrieval circuit is open, so users still get a
sensible (if generic) list instead of an error.
"""

from __future__ import annotations

from core.models import Product, RankedProduct, RankingResult
from recommender.ranking import RankingConfig


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def popularity_ranking(
    products: list[Product], k: int = 5, config: RankingConfig | None = None
) -> RankingResult:
    cfg = config or RankingConfig()
    ranked: list[RankedProduct] = []
    for product in products:
        rating = _clamp01((product.avg_rating - 1.0) / 4.0)
        volume = min(product.review_count / cfg.volume_saturation, 1.0)
        ranked.append(
            RankedProduct(
                product_id=product.product_id,
                title=product.title,
                final_score=round(rating * volume, 6),
                relevance_score=0.0,  # no semantic relevance in the degraded path
                rating_score=round(rating, 6),
                volume_confidence=round(volume, 6),
                avg_rating=product.avg_rating,
                review_count=product.review_count,
                semantic_score=0.0,
                text=product.combined_text,
            )
        )
    ranked.sort(key=lambda r: (r.final_score, r.avg_rating, r.review_count), reverse=True)
    return RankingResult(products=ranked[:k], no_match=False)
