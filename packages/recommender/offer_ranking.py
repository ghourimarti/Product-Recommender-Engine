"""Rating-aware ranking over live shopping offers (aggregator).

Reuses the same blend idea as the catalog recommender, adapted to offers:
    final = relevance_weight * relevance + rating_weight * rating_norm * volume_confidence
where `relevance` comes from the source result position (Google already ordered by relevance),
`rating_norm` from the star rating, and `volume_confidence` from review_count. Our value-add is
re-ranking Google's order by rating quality — so a slightly lower-ranked but far better-rated
product can rise.
"""

from __future__ import annotations

from core.models import Offer, RankedOffer
from recommender.ranking import RankingConfig

# Neutral midpoint for a MISSING signal. Applied to both relevance (offer has no position) and
# rating (offer has no stars), so incomplete data leaves an offer neither promoted nor buried.
# Named for the role it plays rather than for one of its two callers -- it was `_NEUTRAL_RATING`,
# which read as a rating constant even where it stands in for relevance.
_NEUTRAL_SCORE = 0.5


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def rank_offers(offers: list[Offer], config: RankingConfig | None = None) -> list[RankedOffer]:
    cfg = config or RankingConfig()
    if not offers:
        return []

    max_position = max((o.position for o in offers), default=1) or 1
    ranked: list[RankedOffer] = []
    for offer in offers:
        if offer.position:
            relevance = _clamp01(1.0 - (offer.position - 1) / max_position)
        else:
            relevance = _NEUTRAL_SCORE
        rating_norm = _clamp01((offer.rating - 1.0) / 4.0) if offer.rating else _NEUTRAL_SCORE
        volume = min(offer.review_count / cfg.volume_saturation, 1.0)
        final = cfg.relevance_weight * relevance + cfg.rating_weight * rating_norm * volume
        ranked.append(
            RankedOffer(
                offer=offer,
                final_score=round(final, 6),
                relevance_score=round(relevance, 6),
                rating_score=round(rating_norm, 6),
                volume_confidence=round(volume, 6),
            )
        )

    ranked.sort(
        key=lambda r: (r.final_score, r.offer.rating or 0.0, r.offer.review_count), reverse=True
    )
    return ranked
