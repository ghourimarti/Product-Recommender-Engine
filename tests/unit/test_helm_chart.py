"""Contract tests for the Helm chart in ops/helm/p2-recommender.

They render the chart with `helm template` and check invariants that break silently: a Service
whose selector matches no pod has zero endpoints, and a fixed `replicas` under an HPA fights the
HPA on every upgrade. Skipped when the helm binary isn't installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

CHART = Path(__file__).resolve().parents[2] / "ops" / "helm" / "p2-recommender"
ENVS = ["kind", "doks", "eks"]
TAG = "abc1234"
WORKLOAD_KINDS = ("Deployment", "StatefulSet")
SELECTOR_KEYS = {
    "app.kubernetes.io/name",
    "app.kubernetes.io/instance",
    "app.kubernetes.io/component",
}

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm binary not installed")


def _render(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["helm", "template", "p2", str(CHART), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _manifests(env: str, *extra: str) -> list[dict[str, Any]]:
    values = str(CHART / f"values-{env}.yaml")
    result = _render("-f", values, "--set-string", f"image.tag={TAG}", *extra)
    assert result.returncode == 0, result.stderr
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def _of_kind(docs: list[dict[str, Any]], *kinds: str) -> list[dict[str, Any]]:
    return [doc for doc in docs if doc["kind"] in kinds]


def _named(docs: list[dict[str, Any]], kind: str, name: str) -> dict[str, Any]:
    (match,) = [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]
    return match


def test_image_tag_is_required() -> None:
    result = _render("-f", str(CHART / "values-kind.yaml"))
    assert result.returncode != 0
    assert "image.tag is required" in result.stderr


def test_latest_tag_is_rejected() -> None:
    result = _render("-f", str(CHART / "values-kind.yaml"), "--set-string", "image.tag=latest")
    assert result.returncode != 0
    assert "'latest' is not allowed" in result.stderr


def test_numeric_tag_is_rejected() -> None:
    # Plain --set parses an all-digit SHA as a number. The chart must refuse it rather than
    # render a mangled image reference.
    result = _render("-f", str(CHART / "values-kind.yaml"), "--set", "image.tag=1234567")
    assert result.returncode != 0
    assert "--set-string" in result.stderr


@pytest.mark.parametrize("env", ENVS)
def test_selectors_are_standard_and_match_their_pods(env: str) -> None:
    for workload in _of_kind(_manifests(env), *WORKLOAD_KINDS):
        name = workload["metadata"]["name"]
        selector = workload["spec"]["selector"]["matchLabels"]
        pod_labels = workload["spec"]["template"]["metadata"]["labels"]
        assert set(selector) == SELECTOR_KEYS, name
        assert selector.items() <= pod_labels.items(), name


@pytest.mark.parametrize("env", ENVS)
def test_every_service_selects_a_workload(env: str) -> None:
    docs = _manifests(env)
    pod_label_sets = [
        workload["spec"]["template"]["metadata"]["labels"]
        for workload in _of_kind(docs, *WORKLOAD_KINDS)
    ]
    for service in _of_kind(docs, "Service"):
        selector = service["spec"]["selector"]
        assert any(selector.items() <= labels.items() for labels in pod_label_sets), (
            f"Service {service['metadata']['name']} selects no pods"
        )


def test_hpa_owns_api_replicas() -> None:
    docs = _manifests("kind")
    assert "replicas" not in _named(docs, "Deployment", "api")["spec"]
    hpa = _named(docs, "HorizontalPodAutoscaler", "api")
    assert hpa["spec"]["scaleTargetRef"]["name"] == "api"


def test_fixed_replicas_when_hpa_disabled() -> None:
    docs = _manifests("kind", "--set", "api.autoscaling.enabled=false")
    assert _named(docs, "Deployment", "api")["spec"]["replicas"] == 2
    assert not _of_kind(docs, "HorizontalPodAutoscaler")


def test_kind_overlay() -> None:
    docs = _manifests("kind")
    container = _named(docs, "Deployment", "api")["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == f"p2-api:{TAG}"
    assert container["imagePullPolicy"] == "Never"
    qdrant = _named(docs, "StatefulSet", "qdrant")
    assert qdrant["spec"]["volumeClaimTemplates"][0]["spec"]["storageClassName"] == "standard"


def test_registry_prefix_and_trailing_slash() -> None:
    docs = _manifests("doks", "--set-string", "image.registry=registry.example.com/team/")
    container = _named(docs, "Deployment", "web")["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == f"registry.example.com/team/p2-web:{TAG}"
