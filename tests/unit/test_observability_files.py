"""The monitoring files shared by compose and the Helm chart (step 6F).

The alert rules and dashboards live once, in ops/helm/p2-recommender/files/. Compose mounts them
from there and the chart wraps them in a PrometheusRule and a ConfigMap, so both environments
evaluate the same rules. These checks need no helm, so they run in every CI job; the alert
semantics themselves are tested with promtool (tests/promtool/, `make alerts-test`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "ops" / "helm" / "p2-recommender" / "files"
COMPOSE = ROOT / "infra" / "compose" / "docker-compose.observability.yml"


def _alerts() -> dict[str, dict[str, Any]]:
    groups = yaml.safe_load((FILES / "alerts.yaml").read_text(encoding="utf-8"))["groups"]
    return {rule["alert"]: rule for group in groups for rule in group["rules"]}


def test_compose_mounts_the_shared_files() -> None:
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    sources = [
        v.split(":")[0] for name in ("prometheus", "grafana") for v in services[name]["volumes"]
    ]
    shared = [s for s in sources if "ops/helm/p2-recommender/files" in s]
    assert len(shared) == 2  # the rules file and the dashboards directory
    for source in shared:
        assert (COMPOSE.parent / source).resolve().exists(), source


def test_alert_rules_are_complete_and_api_down_survives_scale_to_zero() -> None:
    alerts = _alerts()
    assert len(alerts) == 11
    assert alerts["ApiDown"]["expr"] == 'absent(up{job="p2-api"} == 1)'
    for name, rule in alerts.items():
        assert rule["labels"]["severity"] in {"warning", "critical"}, name
        assert rule["annotations"]["summary"], name


def test_dashboards_are_valid_json_with_unique_uids() -> None:
    dashboards = sorted(FILES.glob("dashboards/*.json"))
    assert dashboards
    uids = [json.loads(path.read_text(encoding="utf-8"))["uid"] for path in dashboards]
    assert len(uids) == len(set(uids))
