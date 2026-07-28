"""(Re)index the product catalog into Qdrant.

uv run python -m retrieval.index
"""

from __future__ import annotations

import json
from pathlib import Path

from core.models import Product
from retrieval.store import QdrantHybridStore

DEFAULT_CATALOG = Path("data/products.json")


def load_catalog(path: Path = DEFAULT_CATALOG) -> list[Product]:
    """Load the product catalog produced by the aggregation step."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in raw]


def main() -> None:
    products = load_catalog()
    store = QdrantHybridStore()
    store.index(products)
    print(f"indexed {len(products)} products into Qdrant (hybrid dense+sparse)")


if __name__ == "__main__":
    main()
