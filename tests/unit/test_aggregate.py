"""Unit tests for review -> product aggregation (Step 2). Pure, no disk I/O."""

from __future__ import annotations

from core.aggregate import aggregate_products
from core.models import Review


def _review(
    product_id: str = "P1",
    title: str = "Prod 1",
    rating: int = 5,
    summary: str = "Great",
    review: str = "good product",
) -> Review:
    return Review(
        product_id=product_id, product_title=title, rating=rating, summary=summary, review=review
    )


def test_groups_by_product_id() -> None:
    reviews = [_review(product_id="A"), _review(product_id="A"), _review(product_id="B")]
    products = aggregate_products(reviews)
    assert {p.product_id for p in products} == {"A", "B"}
    counts = {p.product_id: p.review_count for p in products}
    assert counts == {"A": 2, "B": 1}


def test_avg_rating_and_histogram() -> None:
    reviews = [
        _review(product_id="A", rating=5),
        _review(product_id="A", rating=3),
        _review(product_id="A", rating=4),
    ]
    (product,) = aggregate_products(reviews)
    assert product.avg_rating == 4.0
    assert product.rating_histogram == {1: 0, 2: 0, 3: 1, 4: 1, 5: 1}
    assert sum(product.rating_histogram.values()) == product.review_count


def test_low_ratings_pull_average_down() -> None:
    high = aggregate_products([_review(product_id="A", rating=5)])[0]
    low = aggregate_products([_review(product_id="B", rating=1)])[0]
    assert high.avg_rating > low.avg_rating


def test_representative_reviews_dedup_and_longest_first() -> None:
    reviews = [
        _review(product_id="A", review="short"),
        _review(product_id="A", review="a much longer and more informative review text"),
        _review(product_id="A", review="short"),  # duplicate -> collapsed
    ]
    (product,) = aggregate_products(reviews, n_representative=8)
    assert product.representative_reviews == [
        "a much longer and more informative review text",
        "short",
    ]


def test_combined_text_includes_title_and_reviews() -> None:
    reviews = [_review(product_id="A", title="BoAt Buds", review="great bass")]
    (product,) = aggregate_products(reviews)
    assert "BoAt Buds" in product.combined_text
    assert "great bass" in product.combined_text


def test_rating_bounds_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _review(rating=6)
