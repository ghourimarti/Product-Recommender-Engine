"""(Re)index the product catalog into Qdrant.

uv run python -m retrieval.index                     # always rebuild (local `make seed`)
uv run python -m retrieval.index --skip-if-current   # no-op when Qdrant holds this exact catalog

Every point is stamped with a fingerprint of the catalog file. The Kubernetes seed Job passes
--skip-if-current, so it is safe to run on every deploy: Argo CD runs Helm post-install hooks on
every sync, and a rebuild recreates the collection, briefly emptying the live catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from core.models import Product
from retrieval.store import QdrantHybridStore

DEFAULT_CATALOG = Path("data/products.json")


def load_catalog(path: Path = DEFAULT_CATALOG) -> list[Product]:
    """Load the product catalog produced by the aggregation step."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in raw]


def catalog_fingerprint(path: Path = DEFAULT_CATALOG) -> str:
    """Short content hash of the catalog file: it changes exactly when the catalog does."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="(Re)index the product catalog into Qdrant.")
    parser.add_argument(
        "--skip-if-current",
        action="store_true",
        help="do nothing when Qdrant already holds this exact catalog (safe on every deploy)",
    )
    args = parser.parse_args(argv)
    products = load_catalog()
    fingerprint = catalog_fingerprint()
    store = QdrantHybridStore()
    if args.skip_if_current and store.holds_catalog(fingerprint, len(products)):
        print(f"skipped: Qdrant already holds catalog {fingerprint} ({len(products)} products)")
        return
    store.index(products, catalog=fingerprint)
    print(f"indexed {len(products)} products into Qdrant (hybrid dense+sparse)")
    print(f"catalog fingerprint {fingerprint}")


if __name__ == "__main__":
    main()
