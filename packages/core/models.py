"""Domain models for the recommender (Pydantic v2).

These are the contracts the whole pipeline shares: raw ``Review`` rows are
aggregated into product-level ``Product`` records (the recommender's unit), and
``Citation`` grounds a recommendation back to a real review.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Review(BaseModel):
    """A single raw product review from the source CSV."""

    product_id: str
    product_title: str
    rating: int = Field(ge=1, le=5)
    summary: str = ""
    review: str

    @field_validator("product_id", "product_title", "review")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v.strip()


class Product(BaseModel):
    """Product-level record aggregated from many reviews — the recommender's unit."""

    product_id: str
    title: str
    review_count: int = Field(ge=1)
    avg_rating: float = Field(ge=1.0, le=5.0)
    rating_histogram: dict[int, int]
    representative_reviews: list[str]
    summary_phrases: list[str]
    combined_text: str  # title + representative reviews; the text embedded in Step 3


class Citation(BaseModel):
    """Grounds a recommendation back to a concrete review (used from Step 6)."""

    product_id: str
    title: str
    summary: str
    snippet: str


class RetrievedProduct(BaseModel):
    """A product returned from retrieval, with its semantic score + ranking signals."""

    product_id: str
    title: str
    avg_rating: float
    review_count: int
    semantic_score: float
    text: str


class RankedProduct(BaseModel):
    """A product after rating-aware ranking, with the score components exposed."""

    product_id: str
    title: str
    final_score: float
    relevance_score: float  # clamped retrieval score
    rating_score: float  # normalized avg_rating (1->0, 5->1)
    volume_confidence: float  # review_count saturating multiplier
    avg_rating: float
    review_count: int
    semantic_score: float  # raw retrieval score (pre-clamp)


class RankingResult(BaseModel):
    """Ranked recommendations plus the 'no good match' signal (Decision 21 / F6)."""

    products: list[RankedProduct]
    no_match: bool
