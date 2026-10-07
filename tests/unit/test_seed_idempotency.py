"""The seed Job's skip check: rebuild Qdrant only when the catalog actually changed.

Argo CD runs Helm post-install hooks on every sync, and a rebuild recreates the collection, so a
seed that always rebuilt would blank the live catalog on every deploy.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.config import Settings
from retrieval import index
from retrieval.store import QdrantHybridStore, _product_to_document

ROOT = Path(__file__).resolve().parents[2]


class FakeQdrant:
    """Enough of QdrantClient: `stamps` is one catalog stamp per point; None = no collection."""

    def __init__(self, stamps: list[str | None] | None) -> None:
        self.stamps = stamps

    def collection_exists(self, name: str) -> bool:
        return self.stamps is not None

    def scroll(self, collection_name: str, limit: int, **_: Any) -> tuple[list[Any], None]:
        points = [
            SimpleNamespace(payload={"metadata": {"catalog": stamp} if stamp else {}})
            for stamp in self.stamps or []
        ]
        return points[:limit], None


def _store(stamps: list[str | None] | None) -> QdrantHybridStore:
    store = QdrantHybridStore.__new__(QdrantHybridStore)  # skip __init__: no models, no network
    store._settings = Settings.model_construct(qdrant_collection="products")
    store._client = FakeQdrant(stamps)
    return store


@pytest.mark.parametrize(
    ("stamps", "expected"),
    [
        (None, False),  # no collection yet: the first install must index
        (["abc"] * 9, True),  # exactly this catalog: skip
        (["abc"] * 8, False),  # a point is missing
        (["abc"] * 10, False),  # one point too many (a product was removed from the catalog)
        (["abc"] * 8 + ["old"], False),  # partly another catalog
        ([None] * 9, False),  # indexed before points were stamped
    ],
)
def test_holds_catalog(stamps: list[str | None] | None, expected: bool) -> None:
    assert _store(stamps).holds_catalog("abc", 9) is expected


def test_points_carry_the_catalog_stamp_only_when_given() -> None:
    product = index.load_catalog(ROOT / "data" / "products.json")[0]
    assert _product_to_document(product, "abc").metadata["catalog"] == "abc"
    assert "catalog" not in _product_to_document(product).metadata


def test_fingerprint_follows_the_file_content(tmp_path: Path) -> None:
    catalog = tmp_path / "products.json"
    catalog.write_text("[1]")
    first = index.catalog_fingerprint(catalog)
    assert index.catalog_fingerprint(catalog) == first
    catalog.write_text("[2]")
    assert index.catalog_fingerprint(catalog) != first


def test_main_skips_only_when_asked_and_current(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(ROOT)  # the catalog path is relative, as in the image
    state = {"current": True, "rebuilds": 0}

    class FakeStore:
        def holds_catalog(self, catalog: str, size: int) -> bool:
            return state["current"] is True

        def index(self, products: list[Any], catalog: str = "") -> None:
            assert catalog == index.catalog_fingerprint()
            state["rebuilds"] += 1

    monkeypatch.setattr(index, "QdrantHybridStore", FakeStore)
    index.main(["--skip-if-current"])
    assert state["rebuilds"] == 0 and "skipped" in capsys.readouterr().out
    index.main([])  # `make seed` always rebuilds
    assert state["rebuilds"] == 1
    state["current"] = False
    index.main(["--skip-if-current"])  # the catalog changed: rebuild
    assert state["rebuilds"] == 2
