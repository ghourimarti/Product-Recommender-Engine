"""Contract tests for the Helm chart in ops/helm/p2-recommender.

They render the chart with `helm template` and check invariants that break silently: a Service
whose selector matches no pod has zero endpoints, a fixed `replicas` under an HPA fights the HPA
on every upgrade, a pod that isn't provably non-root fails only at runtime on the node, and a
route that doesn't strip /api sends every API call to a 404. Skipped when helm isn't installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

CHART = Path(__file__).resolve().parents[2] / "ops" / "helm" / "p2-recommender"
ENVS = ["kind", "doks", "eks"]
TAG = "abc1234"
WORKLOAD_KINDS = ("Deployment", "StatefulSet")  # long-running, with selectors and probes
POD_KINDS = (*WORKLOAD_KINDS, "Job")  # everything that creates pods
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
        encoding="utf-8",  # not the locale's: on Windows that's cp1252, which mangles "—"
        check=False,
    )


@cache  # each distinct render runs once per test session
def _rendered(env: str, extra: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    values = str(CHART / f"values-{env}.yaml")
    result = _render("-f", values, "--set-string", f"image.tag={TAG}", *extra)
    assert result.returncode == 0, result.stderr
    return tuple(doc for doc in yaml.safe_load_all(result.stdout) if doc)


def _manifests(env: str, *extra: str) -> list[dict[str, Any]]:
    return list(_rendered(env, extra))


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
    for owner in _of_kind(_manifests(env), *POD_KINDS):
        name = owner["metadata"]["name"]
        pod = owner["spec"]["template"]["spec"]
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
            assert container["resources"]["requests"], name
            assert container["resources"]["limits"], name


@pytest.mark.parametrize("env", ENVS)
def test_every_long_running_container_has_probes(env: str) -> None:
    for workload in _of_kind(_manifests(env), *WORKLOAD_KINDS):
        name = workload["metadata"]["name"]
        for container in workload["spec"]["template"]["spec"]["containers"]:
            assert "readinessProbe" in container and "livenessProbe" in container, name


def test_read_only_roots_get_writable_dirs_where_the_images_write() -> None:
    # Each path was found by running the real image read-only (2026-10-06).
    docs = _manifests("kind")
    expected = {
        ("Deployment", "api"): {"/tmp"},
        ("Deployment", "web"): {"/tmp", "/app/.next/cache"},
        ("Deployment", "dynamodb"): {"/tmp"},
        ("StatefulSet", "qdrant"): {"/qdrant/storage", "/qdrant/snapshots", "/tmp"},
        ("StatefulSet", "redis"): {"/data"},
        ("Job", "seed"): {"/tmp"},
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


def test_web_gets_only_the_clerk_key_from_the_secret() -> None:
    web = _container(_named(_manifests("kind"), "Deployment", "web"))
    assert "envFrom" not in web
    from_secret = {item["name"]: item for item in web["env"] if "valueFrom" in item}
    assert set(from_secret) == {"CLERK_SECRET_KEY"}
    ref = from_secret["CLERK_SECRET_KEY"]["valueFrom"]["secretKeyRef"]
    assert ref["key"] == "CLERK_SECRET_KEY"


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


@pytest.mark.parametrize("env", ENVS)
def test_no_pod_gets_service_link_env_vars(env: str) -> None:
    # On the first kind install the Service named "web" injected WEB_PORT=tcp://<ip>:2012, which
    # overrode the image's WEB_PORT, so Next.js started on port 3000 and never became ready.
    for owner in _of_kind(_manifests(env), *POD_KINDS):
        pod = owner["spec"]["template"]["spec"]
        assert pod["enableServiceLinks"] is False, owner["metadata"]["name"]


def test_web_listens_on_its_container_port() -> None:
    web = _container(_named(_manifests("kind", "--set", "web.port=3100"), "Deployment", "web"))
    env = {item["name"]: item.get("value") for item in web["env"]}
    assert env["WEB_PORT"] == "3100"
    assert web["ports"][0]["containerPort"] == 3100


def test_deployments_spread_across_nodes() -> None:
    docs = _manifests("kind")
    for name in ("api", "web"):
        pod = _named(docs, "Deployment", name)["spec"]["template"]["spec"]
        (spread,) = pod["topologySpreadConstraints"]
        assert spread["topologyKey"] == "kubernetes.io/hostname", name
        assert spread["whenUnsatisfiable"] == "ScheduleAnyway", name
        assert spread["matchLabelKeys"] == ["pod-template-hash"], name


# ── Per-environment wiring (6D) ────────────────────────────────────────────────────────────


def test_http_route_strips_the_api_prefix() -> None:
    docs = _manifests("kind")
    (route,) = _of_kind(docs, "HTTPRoute")
    assert route["spec"]["hostnames"] == ["app.localhost"]
    api_rule, web_rule = route["spec"]["rules"]
    assert api_rule["matches"] == [{"path": {"type": "PathPrefix", "value": "/api"}}]
    assert api_rule["filters"] == [
        {
            "type": "URLRewrite",
            "urlRewrite": {"path": {"type": "ReplacePrefixMatch", "replacePrefixMatch": "/"}},
        }
    ]
    assert api_rule["timeouts"]["request"] == "120s"  # streamed (SSE) answers must not be cut off
    assert web_rule["matches"] == [{"path": {"type": "PathPrefix", "value": "/"}}]
    # Every backend is a Service in the release, on a port that Service exposes.
    services = {s["metadata"]["name"]: s for s in _of_kind(docs, "Service")}
    for rule in route["spec"]["rules"]:
        for ref in rule["backendRefs"]:
            assert ref["port"] in {p["port"] for p in services[ref["name"]]["spec"]["ports"]}


@pytest.mark.parametrize("env", ENVS)
def test_no_ingress_is_rendered(env: str) -> None:
    # The old ALB Ingress forwarded /api/* to FastAPI unstripped; the HTTPRoute replaces it.
    assert not _of_kind(_manifests(env), "Ingress")


@pytest.mark.parametrize(
    ("env", "endpoint", "emulator"),
    [("kind", "http://dynamodb:8000", True), ("doks", "", False), ("eks", "", False)],
)
def test_dynamodb_endpoint_follows_the_environment(env: str, endpoint: str, emulator: bool) -> None:
    docs = _manifests(env)
    env_vars = {
        e["name"]: e.get("value") for e in _container(_named(docs, "Deployment", "api"))["env"]
    }
    # Always set explicitly, so the Secret's compose value (localhost:2003) can't leak in.
    assert env_vars["DYNAMODB_ENDPOINT"] == endpoint
    deployments = {d["metadata"]["name"] for d in _of_kind(docs, "Deployment")}
    assert ("dynamodb" in deployments) is emulator


@pytest.mark.parametrize("env", ENVS)
def test_api_env_names_are_unique(env: str) -> None:
    names = [e["name"] for e in _container(_named(_manifests(env), "Deployment", "api"))["env"]]
    assert len(names) == len(set(names))


def test_seed_job_is_idempotent_and_runs_after_installs_and_upgrades() -> None:
    docs = _manifests("kind")
    job = _named(docs, "Job", "seed")
    # The catalog ships in the api image, so an upgrade may change it: re-check every time.
    assert job["metadata"]["annotations"]["helm.sh/hook"] == "post-install,post-upgrade"
    seed = _container(job)
    # A no-op unless the catalog changed (Argo CD runs this hook on every sync).
    assert seed["command"] == ["python", "-m", "retrieval.index", "--skip-if-current"]
    assert seed["image"] == _container(_named(docs, "Deployment", "api"))["image"]
    install_only = _named(_manifests("kind", "--set", "seed.onUpgrade=false"), "Job", "seed")
    assert install_only["metadata"]["annotations"]["helm.sh/hook"] == "post-install"


def test_network_policies_deny_by_default_and_allow_each_path() -> None:
    docs = _manifests("kind")
    policies = {p["metadata"]["name"]: p for p in _of_kind(docs, "NetworkPolicy")}
    deny = policies["default-deny-ingress"]["spec"]
    assert deny["policyTypes"] == ["Ingress"] and "ingress" not in deny
    # The default-deny covers every pod the chart creates, the seed Job included.
    for owner in _of_kind(docs, *POD_KINDS):
        assert deny["podSelector"]["matchLabels"].items() <= _pod_labels(owner).items()

    def peer_components(policy: str) -> set[str]:
        sources = policies[policy]["spec"]["ingress"][0]["from"]
        return {s["podSelector"]["matchLabels"]["app.kubernetes.io/component"] for s in sources}

    assert peer_components("qdrant-from-api-and-seed") == {"api", "seed"}
    assert peer_components("redis-from-api") == {"api"}
    assert peer_components("dynamodb-from-api") == {"api"}
    gateway = {
        "namespaceSelector": {
            "matchLabels": {"kubernetes.io/metadata.name": "envoy-gateway-system"}
        }
    }
    assert policies["web-from-gateway"]["spec"]["ingress"][0]["from"] == [gateway]
    assert gateway in policies["api-from-gateway-and-monitoring"]["spec"]["ingress"][0]["from"]
    # Every allow targets a workload that exists in the release.
    pod_label_sets = [_pod_labels(w) for w in _of_kind(docs, *WORKLOAD_KINDS)]
    for name, policy in policies.items():
        selector = policy["spec"]["podSelector"]["matchLabels"]
        assert any(selector.items() <= labels.items() for labels in pod_label_sets), name


# ── Monitoring (6F) ────────────────────────────────────────────────────────────────────────


def test_monitoring_objects_render_only_when_enabled() -> None:
    # They need the Prometheus Operator CRDs, so environments opt in.
    assert not _of_kind(_manifests("doks"), "ServiceMonitor", "PrometheusRule")
    docs = _manifests("kind")
    assert len(_of_kind(docs, "ServiceMonitor", "PrometheusRule")) == 2
    assert _named(docs, "ConfigMap", "p2-grafana-dashboards")


def test_service_monitor_scrapes_only_the_api_as_p2_api() -> None:
    docs = _manifests("kind")
    monitor = _named(docs, "ServiceMonitor", "api")
    selector = monitor["spec"]["selector"]["matchLabels"]
    matched = [
        s for s in _of_kind(docs, "Service") if selector.items() <= s["metadata"]["labels"].items()
    ]
    assert [s["metadata"]["name"] for s in matched] == ["api"]
    (endpoint,) = monitor["spec"]["endpoints"]
    assert endpoint["port"] in {p["name"] for p in matched[0]["spec"]["ports"]}
    assert endpoint["path"] == "/metrics"
    # The job name compose uses, so the shared rules and dashboards match unchanged.
    relabel = {"action": "replace", "targetLabel": "job", "replacement": "p2-api"}
    assert relabel in endpoint["relabelings"]


def test_prometheus_rule_is_the_shared_rules_file() -> None:
    rule = _named(_manifests("kind"), "PrometheusRule", "p2-alerts")
    shared = yaml.safe_load((CHART / "files" / "alerts.yaml").read_text(encoding="utf-8"))
    assert rule["spec"]["groups"] == shared["groups"]
    alerts = {r["alert"]: r for group in rule["spec"]["groups"] for r in group["rules"]}
    assert len(alerts) == 10
    # Scaled to zero, the api has no scrape targets and no `up` series: only absent() fires.
    assert alerts["ApiDown"]["expr"].startswith("absent(")


def test_dashboards_reach_the_grafana_sidecar() -> None:
    config_map = _named(_manifests("kind"), "ConfigMap", "p2-grafana-dashboards")
    assert config_map["metadata"]["labels"]["grafana_dashboard"] == "1"
    assert json.loads(config_map["data"]["p2-overview.json"])["uid"] == "p2-overview"


@pytest.mark.parametrize("env", ENVS)
def test_pod_templates_carry_no_version_labels(env: str) -> None:
    # Any pod template change restarts the pods, so version labels there would restart every pod
    # on every chart bump, including the single-replica Qdrant and Redis.
    for owner in _of_kind(_manifests(env), *POD_KINDS):
        labels = _pod_labels(owner)
        assert not {"helm.sh/chart", "app.kubernetes.io/version"} & set(labels), owner["metadata"][
            "name"
        ]
