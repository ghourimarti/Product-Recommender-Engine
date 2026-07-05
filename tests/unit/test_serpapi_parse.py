"""Unit test for SerpApi -> Offer normalization (Step A1). Offline, uses a fixture."""

from __future__ import annotations

import json
from pathlib import Path

from sources.serpapi_source import parse_shopping_results

FIXTURE = Path(__file__).parent.parent / "fixtures" / "serpapi_google_shopping.json"


def test_parse_shopping_results() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    offers = parse_shopping_results(payload)

    # The untitled third result is skipped.
    assert len(offers) == 2

    top = offers[0]
    assert top.title.startswith("Sony WH-1000XM5")
    assert top.price == 348.0
    assert top.store == "Amazon.com"
    assert top.product_url == "https://www.google.com/shopping/product/1111"
    assert top.rating == 4.6
    assert top.review_count == 1200
    assert top.position == 1
    assert "Noise cancelling" in top.snippet


def test_parse_empty_payload() -> None:
    assert parse_shopping_results({}) == []
