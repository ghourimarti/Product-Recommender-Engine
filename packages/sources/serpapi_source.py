"""SerpApi (Google Shopping) source — live product offers for the aggregator.

`parse_shopping_results` (pure) normalizes SerpApi's JSON into our `Offer` model and is
unit-tested offline against a fixture. `search_offers` makes the one live HTTP call. Keep
live calls minimal — SerpApi search quota is metered/paid; the cache layer (Step A3) exists
precisely to avoid repeat calls.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.config import Settings, get_settings
from core.models import Offer

SERPAPI_URL = "https://serpapi.com/search.json"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _snippet(item: dict[str, Any]) -> str:
    extensions = item.get("extensions")
    if isinstance(extensions, list):
        return " · ".join(str(e) for e in extensions)
    return str(item.get("snippet", "") or "")


def parse_shopping_results(payload: dict[str, Any]) -> list[Offer]:
    """Normalize SerpApi google_shopping `shopping_results` into Offers (skips untitled)."""
    offers: list[Offer] = []
    for item in payload.get("shopping_results", []):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        position = int(item.get("position") or 0)
        offers.append(
            Offer(
                product_id=str(item.get("product_id") or position or title),
                title=title,
                price=_to_float(item.get("extracted_price")),
                currency="USD",
                store=str(item.get("source", "")),
                product_url=str(item.get("product_link") or item.get("link") or ""),
                thumbnail=item.get("thumbnail"),
                rating=_to_float(item.get("rating")),
                review_count=int(item.get("reviews") or 0),
                snippet=_snippet(item),
                position=position,
            )
        )
    return offers


def search_offers(query: str, num: int = 10, settings: Settings | None = None) -> list[Offer]:
    """One live SerpApi Google Shopping search -> list of Offers."""
    settings = settings or get_settings()
    if not settings.serpapi_api_key:
        raise RuntimeError("SERPAPI_API_KEY not set")
    params: dict[str, str | int] = {
        "engine": "google_shopping",
        "q": query,
        "api_key": settings.serpapi_api_key,
        "num": num,
        "gl": settings.serpapi_gl,
        "hl": settings.serpapi_hl,
    }
    response = httpx.get(SERPAPI_URL, params=params, timeout=20.0)
    response.raise_for_status()
    return parse_shopping_results(response.json())
