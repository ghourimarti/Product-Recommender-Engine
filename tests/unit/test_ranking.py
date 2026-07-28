"""Unit tests for the rating-aware ranking blend. Pure, no services."""

from __future__ import annotations

from core.models import RetrievedProduct
from recommender.ranking import RankingConfig, rank_products


def _rp(
    product_id: str = "A",
    title: str = "Prod",
    semantic: float = 0.8,
    rating: float = 4.5,
    review_count: int = 50,
) -> RetrievedProduct:
    return RetrievedProduct(
        product_id=product_id,
        title=title,
        avg_rating=rating,
        review_count=review_count,
        semantic_score=semantic,
        text="...",
    )


def test_empty_candidates_is_no_match() -> None:
    result = rank_products([])
    assert result.products == []
    assert result.no_match is True


def test_higher_relevance_wins_when_ratings_equal() -> None:
    result = rank_products(
        [
            _rp(product_id="low", semantic=0.3, rating=4.5),
            _rp(product_id="high", semantic=0.9, rating=4.5),
        ]
    )
    assert result.products[0].product_id == "high"


def test_rating_breaks_tie_when_relevance_equal() -> None:
    result = rank_products(
        [
            _rp(product_id="worse", semantic=0.5, rating=4.0),
            _rp(product_id="better", semantic=0.5, rating=5.0),
        ]
    )
    assert result.products[0].product_id == "better"


def test_low_review_volume_discounts_high_rating() -> None:
    # A: perfect rating but only 2 reviews; B: slightly lower rating, 50 reviews.
    result = rank_products(
        [
            _rp(product_id="thin", semantic=0.5, rating=5.0, review_count=2),
            _rp(product_id="solid", semantic=0.5, rating=4.5, review_count=50),
        ]
    )
    assert result.products[0].product_id == "solid"


def test_no_match_when_best_relevance_below_floor() -> None:
    result = rank_products([_rp(semantic=0.01)], RankingConfig(min_relevance=0.05))
    assert result.no_match is True


def test_match_when_relevance_above_floor() -> None:
    result = rank_products([_rp(semantic=0.5)], RankingConfig(min_relevance=0.05))
    assert result.no_match is False


def test_scores_stay_in_unit_interval() -> None:
    result = rank_products([_rp(semantic=1.0, rating=5.0, review_count=1000)])
    product = result.products[0]
    assert 0.0 <= product.final_score <= 1.0
    assert 0.0 <= product.relevance_score <= 1.0
    assert 0.0 <= product.rating_score <= 1.0
    assert 0.0 <= product.volume_confidence <= 1.0
