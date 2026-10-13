"""The generated Grafana dashboards: one definition, two formats, nothing stale or dangling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ops.observability.grafana import build_dashboards as bd


def _layout_names(layout: dict[str, Any]) -> list[str]:
    """Every element a v2 layout references, at any nesting depth."""
    spec = layout["spec"]
    if layout["kind"] == "GridLayout":
        return [item["spec"]["element"]["name"] for item in spec["items"]]
    return [name for row in spec["rows"] for name in _layout_names(row["spec"]["layout"])]


def test_committed_dashboards_are_up_to_date() -> None:
    # Edit build_dashboards.py, then run it: the JSON is generated, never hand-edited.
    for path, payload in bd.build():
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == json.loads(json.dumps(payload)), f"{path.name} is stale: regenerate it"


@pytest.mark.parametrize("make", bd.DASHBOARDS, ids=lambda m: m.__name__)
def test_v2_layout_places_every_panel_exactly_once(make: Any) -> None:
    payload = bd.to_v2(make())
    names = _layout_names(payload["spec"]["layout"])
    assert sorted(names) == sorted(payload["spec"]["elements"])


@pytest.mark.parametrize("make", bd.DASHBOARDS, ids=lambda m: m.__name__)
def test_every_panel_is_described_and_fits_the_grid(make: Any) -> None:
    for panel in bd.walk(make().sections):
        assert panel.description, panel.title
        assert 1 <= panel.w <= 24 and panel.h >= 3, panel.title


def test_sections_nest_and_collapse() -> None:
    # The point of the v2 format: "1 — ..." holding "1.1 — ...", some collapsed by default.
    layout = bd.to_v2(bd.health())["spec"]["layout"]
    top = {row["spec"]["title"]: row["spec"] for row in layout["spec"]["rows"]}
    services = top["1 — Is every service answering?"]["layout"]
    assert services["kind"] == "RowsLayout"
    subs = {row["spec"]["title"]: row["spec"]["collapse"] for row in services["spec"]["rows"]}
    assert subs["1.1 — Services (health probe every 15 s)"] is False
    assert subs["1.3 — How fast each service answers its probe"] is True


def test_kubernetes_gets_the_same_queries_in_the_classic_format() -> None:
    v1 = json.loads((bd.SHARED / "p2-api-llm.json").read_text(encoding="utf-8"))
    v2 = json.loads((bd.COMPOSE / "p2-api-llm.json").read_text(encoding="utf-8"))
    assert "panels" in v1 and v2["apiVersion"].startswith("dashboard.grafana.app/")
    assert sorted(bd.expressions(v1)) == sorted(bd.expressions(v2))


def test_uids_are_unique_and_compose_has_only_generated_dashboards() -> None:
    uids = [make().uid for make in bd.DASHBOARDS]
    assert len(uids) == len(set(uids))
    on_disk = {p.stem for p in Path(bd.COMPOSE).glob("*.json")}
    assert on_disk == set(uids)


def test_bars_are_instant_and_idle_panels_say_why() -> None:
    for make in bd.DASHBOARDS:
        for panel in bd.walk(make().sections):
            if panel.kind == "bargauge":
                assert all(t.instant for t in panel.targets), (
                    panel.title
                )  # "right now", not a range
            if panel.idle_ok and panel.kind == "timeseries":
                assert panel.defaults.get("noValue"), panel.title  # never a bare "No data"
