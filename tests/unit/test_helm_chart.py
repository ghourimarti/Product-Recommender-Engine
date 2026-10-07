"""Contract tests for the Helm chart in ops/helm/p2-recommender.

They render the chart with `helm template` and check invariants that break silently: a Service
whose selector matches no pod has zero endpoints, a fixed `replicas` under an HPA fights the HPA
on every upgrade, and a pod that isn't provably non-root fails only at runtime, on the node.
Skipped when the helm binary isn't installed.
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


def _container(workload: dict[str, Any]) -> dict[str, Any]:
    containers: list[dict[str, Any]] = workload["spec"]["template"]["spec"]["containers"]
    (container,) = containers
    return container


def _pod_labels(workload: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = workload["spec"]["template"]["metadata"]["labels"]
    return labels


# ── Image tags (6B) ────────────────────────────────────────────────────────────────────────


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


def test_registry_prefix_and_trailing_slash() -> None:
    docs = _manifests("doks", "--set-string", "image.registry=registry.example.com/team/")
    container = _container(_named(docs, "Deployment", "web"))
    assert container["image"] == f"registry.example.com/team/p2-web:{TAG}"


# ── Selectors and wiring (6B) ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("env", ENVS)
def test_selectors_are_standard_and_match_their_pods(env: str) -> None:
    for workload in _of_kind(_manifests(env), *WORKLOAD_KINDS):
        name = workload["metadata"]["name"]
        selector = workload["spec"]["selector"]["matchLabels"]
        assert set(selector) == SELECTOR_KEYS, name
        assert selector.items() <= _pod_labels(workload).items(), name


@pytest.mark.parametrize("env", ENVS)
def test_every_service_selects_a_workload(env: str) -> None:
    docs = _manifests(env)
    pod_label_sets = [_pod_labels(w) for w in _of_kind(docs, *WORKLOAD_KINDS)]
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
    container = _container(_named(docs, "Deployment", "api"))
    assert container["image"] == f"p2-api:{TAG}"
    assert container["imagePullPolicy"] == "Never"
    for name in ("qdrant", "redis"):
        claim = _named(docs, "StatefulSet", name)["spec"]["volumeClaimTemplates"][0]
        assert claim["spec"]["storageClassName"] == "standard", name


# ── Hardening (6C) ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("env", ENVS)
def test_every_pod_runs_the_restricted_profile(env: str) -> None:
    for workload in _of_kind(_manifests(env), *WORKLOAD_KINDS):
        name = workload["metadata"]["name"]
        pod = workload["spec"]["template"]["spec"]
        security = pod["securityContext"]
        assert security["runAsNonRoot"] is True, name
        # Numeric, because the kubelet can't verify that a named image USER isn't root.
        assert isinstance(security["runAsUser"], int) and security["runAsUser"] > 0, name
        assert security["seccompProfile"]["type"] == "RuntimeDefault", name
        assert pod["automountServiceAccountToken"] is False, name
        for container in pod["containers"]:
            locked = container["securityContext"]
            assert locked["allowPrivilegeEscalation"] is False, name
            assert locked["capabilities"]["drop"] == ["ALL"], name
            assert locked["readOnlyRootFilesystem"] is True, name


@pytest.mark.parametrize("env", ENVS)
def test_every_container_has_probes_and_resources(env: str) -> None:
    for workload in _of_kind(_manifests(env), *WORKLOAD_KINDS):
        name = workload["metadata"]["name"]
        for container in workload["spec"]["template"]["spec"]["containers"]:
            assert "readinessProbe" in container and "livenessProbe" in container, name
            assert container["resources"]["requests"], name
            assert container["resources"]["limits"], name


def test_read_only_roots_get_writable_dirs_where_the_images_write() -> None:
    # Each path was found by running the real image read-only (2026-10-06).
    docs = _manifests("kind")
    expected = {
        ("Deployment", "api"): {"/tmp"},
        ("Deployment", "web"): {"/tmp", "/app/.next/cache"},
        ("StatefulSet", "qdrant"): {"/qdrant/storage", "/qdrant/snapshots", "/tmp"},
        ("StatefulSet", "redis"): {"/data"},
    }
    for (kind, name), paths in expected.items():
        mounts = {m["mountPath"] for m in _container(_named(docs, kind, name))["volumeMounts"]}
        assert paths <= mounts, (name, paths - mounts)


def test_api_survives_a_slow_start_and_drains_gracefully() -> None:
    api = _container(_named(_manifests("kind"), "Deployment", "api"))
    startup = api["startupProbe"]
    # The hardened api took 28 s to become healthy; leave generous headroom.
    assert startup["periodSeconds"] * startup["failureThreshold"] >= 120
    assert api["lifecycle"]["preStop"]["sleep"]["seconds"] > 0


def test_web_gets_only_the_clerk_key() -> None:
    web = _container(_named(_manifests("kind"), "Deployment", "web"))
    assert "envFrom" not in web
    env = {item["name"]: item for item in web["env"]}
    assert set(env) == {"CLERK_SECRET_KEY"}
    assert env["CLERK_SECRET_KEY"]["valueFrom"]["secretKeyRef"]["key"] == "CLERK_SECRET_KEY"


def test_qdrant_enforces_the_api_key_from_the_secret() -> None:
    qdrant = _container(_named(_manifests("kind"), "StatefulSet", "qdrant"))
    env = {item["name"]: item for item in qdrant["env"]}
    ref = env["QDRANT__SERVICE__API_KEY"]["valueFrom"]["secretKeyRef"]
    assert ref["key"] == "QDRANT_API_KEY"
    # The health endpoints answer without the key, so plain httpGet probes stay valid.
    assert qdrant["readinessProbe"]["httpGet"]["path"] == "/readyz"


def test_redis_persists_to_its_volume() -> None:
    redis = _named(_manifests("kind"), "StatefulSet", "redis")
    container = _container(redis)
    assert "--appendonly" in container["args"]
    data_mount = next(m for m in container["volumeMounts"] if m["mountPath"] == "/data")
    assert data_mount["name"] == redis["spec"]["volumeClaimTemplates"][0]["metadata"]["name"]


@pytest.mark.parametrize("env", ENVS)
def test_statefulsets_have_headless_governing_services(env: str) -> None:
    docs = _manifests(env)
    for statefulset in _of_kind(docs, "StatefulSet"):
        service = _named(docs, "Service", statefulset["spec"]["serviceName"])
        assert service["spec"]["clusterIP"] == "None"
        assert service["spec"]["selector"].items() <= _pod_labels(statefulset).items()


def test_pdbs_cover_the_replicated_workloads() -> None:
    docs = _manifests("kind")
    budgets = {pdb["metadata"]["name"]: pdb for pdb in _of_kind(docs, "PodDisruptionBudget")}
    assert set(budgets) == {"api", "web"}
    for name, pdb in budgets.items():
        pods = _pod_labels(_named(docs, "Deployment", name))
        assert pdb["spec"]["selector"]["matchLabels"].items() <= pods.items(), name
        assert pdb["spec"]["maxUnavailable"] == 1, name


def test_deployments_spread_across_nodes() -> None:
    docs = _manifests("kind")
    for name in ("api", "web"):
        pod = _named(docs, "Deployment", name)["spec"]["template"]["spec"]
        (spread,) = pod["topologySpreadConstraints"]
        assert spread["topologyKey"] == "kubernetes.io/hostname", name
        assert spread["whenUnsatisfiable"] == "ScheduleAnyway", name
        assert spread["matchLabelKeys"] == ["pod-template-hash"], name
