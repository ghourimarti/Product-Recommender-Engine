"""`make verify`: call every P2 component and print PASS / WARN / FAIL / SKIP for each.

    uv run python -m ops.stack.verify            # read-only; spends nothing
    uv run python -m ops.stack.verify --live     # + one tiny call per LLM provider (~$0.0001)

Read-only: it sends no chat, writes nothing and spends no SerpApi search. WARN means "works,
but there is nothing to show yet" (no traces before the first chat, say) or "works, with a
caveat". FAIL means broken. Exit code 1 when anything FAILs.

Secrets: requests carry the keys they need, but no key is ever printed. Every message passes
through redact(), which blanks every secret-looking value from .env.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import boto3
import httpx
import redis
import yaml

from infra.kind.image_tag import image_tag
from ops.stack.catalog import ROOT, KindState, kind_clusters, load_env, run

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
DASHBOARD_DIRS = (
    ROOT / "ops/helm/p2-recommender/files/dashboards",
    ROOT / "ops/observability/grafana/dashboards",
)
ALERTS = ROOT / "ops/helm/p2-recommender/files/alerts.yaml"
CATALOG = ROOT / "data/products.json"
# Counters that only exist once their event has happened (an outage, a block, an OOM kill).
EVENT_METRICS = re.compile(
    r"\b(source_unavailable_total|guardrail_blocks_total|container_oom_events_total)\b"
)
SECRET_HINT = re.compile(r"KEY|SECRET|PASSWORD|AUTH|TOKEN")


@dataclass(frozen=True)
class Result:
    status: str
    detail: str


Check = Callable[[], Result]


class Verifier:
    def __init__(self, env: Mapping[str, str], cluster: str, live: bool) -> None:
        self.env = env
        self.cluster = cluster
        self.live = live
        self.http = httpx.Client(timeout=15)
        self.secrets = sorted(
            {v for k, v in env.items() if v and len(v) >= 6 and SECRET_HINT.search(k)},
            key=len,
            reverse=True,
        )

    # ---- helpers ----------------------------------------------------------------------------

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "<redacted>")
        return text

    def url(self, port_key: str, path: str = "") -> str:
        return f"http://127.0.0.1:{self.env[port_key]}{path}"

    def get(self, port_key: str, path: str, **kwargs: Any) -> httpx.Response:
        return self.http.get(self.url(port_key, path), **kwargs)

    def prom(self, query: str) -> list[dict[str, Any]]:
        res = self.get("PROMETHEUS_PORT", "/api/v1/query", params={"query": query}).json()
        if res.get("status") != "success":
            raise RuntimeError(res.get("error", "query failed"))
        return list(res["data"]["result"])

    # ---- APP --------------------------------------------------------------------------------

    def web_home(self) -> Result:
        r = self.get("WEB_PORT", "/")
        ok = r.status_code == 200 and "<html" in r.text.lower()
        return Result(
            PASS if ok else FAIL, f"HTTP {r.status_code}, {len(r.content) // 1024} KB HTML"
        )

    def web_sign_in(self) -> Result:
        r = self.get("WEB_PORT", "/sign-in")
        return Result(
            PASS if r.status_code == 200 else FAIL, f"HTTP {r.status_code} (Clerk sign-in page)"
        )

    def api_health(self) -> Result:
        r = self.get("API_PORT", "/health")
        ok = r.status_code == 200 and r.json().get("status") == "ok"
        return Result(PASS if ok else FAIL, f"HTTP {r.status_code} {r.text[:80]}")

    def api_docs(self) -> Result:
        r = self.get("API_PORT", "/openapi.json")
        paths = sorted(r.json().get("paths", {})) if r.status_code == 200 else []
        return Result(PASS if paths else FAIL, f"{len(paths)} routes: {', '.join(paths)}")

    def api_metrics(self) -> Result:
        text = self.get("API_PORT", "/metrics").text
        wanted = (
            "http_requests_total",
            "llm_requests_total",
            "llm_tokens_total",
            "cache_hits_total",
        )
        missing = [
            m for m in wanted if f"# HELP {m.removesuffix('_total')}" not in text and m not in text
        ]
        return Result(
            FAIL if missing else PASS,
            f"missing: {missing}" if missing else "app + LLM metrics exported",
        )

    def api_auth(self) -> Result:
        r = self.http.post(self.url("API_PORT", "/recommend"), json={"query": "headphones", "k": 3})
        return Result(
            PASS if r.status_code == 401 else FAIL, f"no token -> HTTP {r.status_code} (want 401)"
        )

    # ---- DATA -------------------------------------------------------------------------------

    def qdrant(self) -> Result:
        headers = {"api-key": self.env["QDRANT_API_KEY"]} if self.env.get("QDRANT_API_KEY") else {}
        coll = self.env["QDRANT_COLLECTION"]
        r = self.get("QDRANT_HTTP_PORT", f"/collections/{coll}", headers=headers)
        if r.status_code == 404:
            return Result(FAIL, f"collection '{coll}' missing: make seed")
        info = r.json()["result"]
        points = info.get("points_count") or 0
        expected = len(json.loads(CATALOG.read_text(encoding="utf-8")))
        status = (
            PASS
            if points == expected and info.get("status") == "green"
            else WARN
            if points
            else FAIL
        )
        return Result(
            status, f"'{coll}' {info.get('status')}, {points} points (catalog has {expected})"
        )

    def qdrant_auth(self) -> Result:
        if not self.env.get("QDRANT_API_KEY"):
            return Result(WARN, "no QDRANT_API_KEY: Qdrant is open to anything on this machine")
        r = self.get("QDRANT_HTTP_PORT", "/collections")
        return Result(
            PASS if r.status_code == 401 else FAIL, f"no key -> HTTP {r.status_code} (want 401)"
        )

    def dynamodb(self) -> Result:
        client = boto3.client(
            "dynamodb",
            endpoint_url=self.url("DYNAMODB_PORT"),
            region_name=self.env["AWS_REGION"],
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
        tables = client.list_tables()["TableNames"]
        table = self.env["DYNAMODB_TABLE"]
        if table not in tables:
            return Result(WARN, f"up; table '{table}' appears on the first chat (in-memory store)")
        count = client.describe_table(TableName=table)["Table"].get("ItemCount", 0)
        return Result(PASS, f"table '{table}', ~{count} items")

    def redis_app(self) -> Result:
        client = redis.Redis(host="127.0.0.1", port=int(self.env["REDIS_PORT"]), socket_timeout=5)
        client.ping()
        return Result(PASS, f"PING ok, {client.dbsize()} keys")

    # ---- OBSERVABILITY ----------------------------------------------------------------------

    def prometheus_targets(self) -> Result:
        targets = self.get("PROMETHEUS_PORT", "/api/v1/targets").json()["data"]["activeTargets"]
        down = [
            f"{t['labels'].get('job')}/{t['labels'].get('instance')}"
            for t in targets
            if t["health"] != "up"
        ]
        if down:
            return Result(FAIL, f"{len(down)}/{len(targets)} targets down: {', '.join(down)}")
        return Result(PASS, f"{len(targets)}/{len(targets)} scrape targets up")

    def prometheus_probes(self) -> Result:
        rows = self.prom("probe_success")
        failed = [
            r["metric"].get("service", r["metric"].get("instance"))
            for r in rows
            if r["value"][1] != "1"
        ]
        if not rows:
            return Result(FAIL, "no blackbox probe results")
        if failed:
            return Result(FAIL, f"probes failing: {', '.join(failed)}")
        return Result(PASS, f"{len(rows)}/{len(rows)} blackbox probes succeed")

    def prometheus_rules(self) -> Result:
        groups = self.get("PROMETHEUS_PORT", "/api/v1/rules").json()["data"]["groups"]
        loaded = sum(len(g["rules"]) for g in groups)
        expected = sum(
            len(g["rules"]) for g in yaml.safe_load(ALERTS.read_text(encoding="utf-8"))["groups"]
        )
        firing = sorted(
            {r["labels"]["alertname"] for r in self.prom('ALERTS{alertstate="firing"}')}
        )
        status = FAIL if loaded != expected else WARN if firing else PASS
        detail = f"{loaded}/{expected} alert rules loaded"
        return Result(
            status, detail + (f"; FIRING: {', '.join(firing)}" if firing else "; none firing")
        )

    def grafana(self) -> Result:
        health = self.get("GRAFANA_PORT", "/api/health").json()
        expected = {
            json.loads(p.read_text(encoding="utf-8"))["uid"]
            for d in DASHBOARD_DIRS
            for p in d.glob("*.json")
        }
        found = {
            d["uid"]
            for d in self.get("GRAFANA_PORT", "/api/search", params={"type": "dash-db"}).json()
        }
        missing = expected - found
        status = PASS if health.get("database") == "ok" and not missing else FAIL
        ours = len(expected & found)
        detail = f"v{health.get('version')}, no login; {ours}/{len(expected)} P2 dashboards"
        return Result(status, detail + (f"; missing {sorted(missing)}" if missing else ""))

    def grafana_datasources(self) -> Result:
        prom = self.get("GRAFANA_PORT", "/api/datasources/uid/prometheus/health").json()
        # The Jaeger plugin has no backend health check; query through Grafana's proxy instead.
        jaeger = self.get("GRAFANA_PORT", "/api/datasources/proxy/uid/jaeger/api/services")
        services = (jaeger.json().get("data") or []) if jaeger.status_code == 200 else []
        ok = prom.get("status") == "OK" and jaeger.status_code == 200
        return Result(
            PASS if ok else FAIL, f"Prometheus {prom.get('status')}; Jaeger via proxy: {services}"
        )

    def grafana_panels(self) -> Result:
        now, total, empty = time.time(), 0, []
        for folder in DASHBOARD_DIRS:
            for path in sorted(folder.glob("*.json")):
                dash = json.loads(path.read_text(encoding="utf-8"))
                for panel in dash["panels"]:
                    for target in panel.get("targets", []):
                        expr = target.get("expr")
                        if not expr or EVENT_METRICS.search(expr):
                            continue
                        total += 1
                        res = self.get(
                            "PROMETHEUS_PORT",
                            "/api/v1/query_range",
                            params={"query": expr, "start": now - 1800, "end": now, "step": 60},
                        ).json()
                        values = [
                            float(v)
                            for s in res.get("data", {}).get("result", [])
                            for _, v in s["values"]
                        ]
                        if res.get("status") != "success" or not [
                            v for v in values if not math.isnan(v)
                        ]:
                            empty.append(f"{dash['uid']}/{panel['title']}")
        if not empty:
            return Result(PASS, f"{total}/{total} panel queries return data (last 30 min)")
        panels = list(dict.fromkeys(empty))  # a panel with p50 + p95 targets is listed once
        shown = ", ".join(panels[:4]) + (" ..." if len(panels) > 4 else "")
        return Result(
            WARN, f"{len(empty)}/{total} queries empty (normal with no traffic in 30 min): {shown}"
        )

    def jaeger(self) -> Result:
        service = self.env["OTEL_SERVICE_NAME"]
        services = self.get("JAEGER_UI_PORT", "/api/services").json().get("data") or []
        if service not in services:
            return Result(WARN, f"up; no traces from '{service}' yet (call the API once)")
        traces = self.get(
            "JAEGER_UI_PORT", "/api/traces", params={"service": service, "limit": 20}
        ).json()
        return Result(PASS, f"'{service}' traced, {len(traces.get('data') or [])} recent traces")

    def langfuse(self) -> Result:
        r = self.get("LANGFUSE_UI_PORT", "/api/public/health")
        return Result(PASS if r.status_code == 200 else FAIL, f"HTTP {r.status_code} {r.text[:60]}")

    def langfuse_autologin(self) -> Result:
        r = self.http.get(self.url("LANGFUSE_AUTOLOGIN_PORT", "/"), follow_redirects=False)
        cookie = "next-auth.session-token" in r.headers.get("set-cookie", "")
        where = r.headers.get("location", "")
        ok = r.status_code == 302 and cookie and "/project/" in where
        return Result(
            PASS if ok else FAIL, f"HTTP {r.status_code}, session cookie {cookie}, -> {where}"
        )

    def langfuse_traces(self) -> Result:
        auth = (self.env["LANGFUSE_PUBLIC_KEY"], self.env["LANGFUSE_SECRET_KEY"])
        r = self.get("LANGFUSE_UI_PORT", "/api/public/traces", params={"limit": 1}, auth=auth)
        if r.status_code != 200:
            return Result(FAIL, f"project keys rejected: HTTP {r.status_code}")
        total = r.json().get("meta", {}).get("totalItems", 0)
        if not total:
            return Result(WARN, "keys work; no LLM trace yet (ask the web app something)")
        return Result(PASS, f"project keys work; {total} LLM traces stored")

    def redisinsight(self) -> Result:
        dbs = self.get("REDISINSIGHT_PORT", "/api/databases").json()
        names = []
        for db in dbs:
            r = self.get("REDISINSIGHT_PORT", f"/api/databases/{db['id']}/connect", timeout=30)
            names.append(
                f"{db['name']} {'connected' if r.status_code == 200 else f'HTTP {r.status_code}'}"
            )
        ok = len(dbs) >= 2 and all(n.endswith("connected") for n in names)
        return Result(PASS if ok else FAIL, "; ".join(names) or "no databases registered")

    def cadvisor(self) -> Result:
        r = self.get("CADVISOR_PORT", "/healthz")
        seen = self.prom('count(container_last_seen{name=~"p2-.+"})')
        count = int(float(seen[0]["value"][1])) if seen else 0
        return Result(
            PASS if r.status_code == 200 and count else FAIL, f"healthy; sees {count} p2 containers"
        )

    # ---- LANGFUSE STORES --------------------------------------------------------------------

    def postgres(self) -> Result:
        e = self.env
        sql = "select count(*) from projects"
        res = run(
            [
                "docker",
                "exec",
                "p2-langfuse-postgres",
                "psql",
                "-U",
                e["LANGFUSE_POSTGRES_USER"],
                "-d",
                e["LANGFUSE_POSTGRES_DB"],
                "-tAc",
                sql,
            ],
            30,
        )
        if res is None or res.returncode != 0:
            return Result(
                FAIL, self.redact((res.stderr if res else "docker unavailable").strip()[:120])
            )
        return Result(PASS, f"accepts logins; {res.stdout.strip()} Langfuse project(s)")

    def clickhouse(self) -> Result:
        auth = (self.env["LANGFUSE_CLICKHOUSE_USER"], self.env["LANGFUSE_CLICKHOUSE_PASSWORD"])
        r = self.get(
            "LANGFUSE_CLICKHOUSE_HTTP_PORT",
            "/",
            params={"query": "SELECT count() FROM traces"},
            auth=auth,
        )
        if r.status_code != 200:
            return Result(FAIL, f"HTTP {r.status_code} {self.redact(r.text[:100])}")
        return Result(PASS, f"login ok; {r.text.strip()} rows in traces")

    def redis_langfuse(self) -> Result:
        client = redis.Redis(
            host="127.0.0.1",
            port=int(self.env["LANGFUSE_REDIS_PORT"]),
            password=self.env["LANGFUSE_REDIS_AUTH"],
            socket_timeout=5,
        )
        client.ping()
        return Result(PASS, f"AUTH + PING ok, {client.dbsize()} keys")

    def minio(self) -> Result:
        live = self.get("LANGFUSE_MINIO_API_PORT", "/minio/health/live")
        s3 = boto3.client(
            "s3",
            endpoint_url=self.url("LANGFUSE_MINIO_API_PORT"),
            aws_access_key_id=self.env["LANGFUSE_MINIO_ROOT_USER"],
            aws_secret_access_key=self.env["LANGFUSE_MINIO_ROOT_PASSWORD"],
            region_name="us-east-1",
        )
        keys = s3.list_objects_v2(Bucket="langfuse", MaxKeys=1000).get("KeyCount", 0)
        return Result(
            PASS if live.status_code == 200 else FAIL,
            f"live; bucket 'langfuse' holds {keys} objects",
        )

    # ---- LLM --------------------------------------------------------------------------------

    def provider(self, name: str, key: str, call: Callable[[str], httpx.Response]) -> Check:
        def check() -> Result:
            secret = self.env.get(key, "")
            if not secret:
                return Result(WARN, f"{key} not set: this tier is skipped")
            if not self.live:
                return Result(SKIP, "key set; LIVE=1 makes one tiny call")
            r = call(secret)
            if r.status_code == 200:
                note = r.headers.get("x-p2-note")
                return Result(PASS, f"{name} answered (HTTP 200)" + (f"; {note}" if note else ""))
            return Result(FAIL, f"HTTP {r.status_code}: {self.redact(r.text[:160])}")

        return check

    def groq(self, key: str) -> httpx.Response:
        return self.http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": self.env["GROQ_MODEL"],
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 3,
            },
        )

    def openai(self, key: str) -> httpx.Response:
        return self.http.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": self.env["OPENAI_MODEL"],
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 3,
            },
        )

    def embeddings(self, key: str) -> httpx.Response:
        return self.http.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": self.env["EMBEDDING_MODEL"], "input": "ping"},
        )

    def anthropic(self, key: str) -> httpx.Response:
        return self.http.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.env["ANTHROPIC_MODEL"],
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 3,
            },
        )

    def serpapi(self, key: str) -> httpx.Response:
        # The account endpoint is free: it reports the plan without spending a search.
        r = self.http.get("https://serpapi.com/account.json", params={"api_key": key})
        if r.status_code == 200:
            left = r.json().get("total_searches_left")
            r = httpx.Response(200, headers={"x-p2-note": f"{left} searches left this month"})
        return r

    def llm_provider_metrics(self) -> Result:
        rows = self.prom("sum by (provider, status) (increase(llm_requests_total[24h]))")
        if not rows:
            return Result(WARN, "no LLM call in the last 24 h (ask the web app something)")
        stats = ", ".join(
            f"{r['metric']['provider']} {r['metric']['status']}={float(r['value'][1]):.0f}"
            for r in rows
        )
        failing = sorted({r["metric"]["provider"] for r in rows if r["metric"]["status"] != "ok"})
        if failing:
            return Result(
                WARN, f"last 24 h: {stats}; failing: {', '.join(failing)} (check the key)"
            )
        return Result(PASS, f"last 24 h: {stats}")

    # ---- KUBERNETES -------------------------------------------------------------------------

    def kind_state(self) -> KindState:
        return kind_clusters().get(self.cluster, KindState(self.cluster))

    def kind_nodes(self) -> Result:
        state = self.kind_state()
        if not state.running:
            return Result(SKIP, f"cluster '{self.cluster}' {state.label} (make kind-start)")
        res = run(
            ["kubectl", "--context", f"kind-{self.cluster}", "get", "nodes", "-o", "json"], 30
        )
        if res is None or res.returncode != 0:
            return Result(
                FAIL, "kubectl can't reach the cluster: make kind-start re-exports the kubeconfig"
            )
        nodes = json.loads(res.stdout)["items"]
        ready = [
            n
            for n in nodes
            if any(
                c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"]
            )
        ]
        return Result(
            PASS if len(ready) == len(nodes) else FAIL, f"{len(ready)}/{len(nodes)} nodes Ready"
        )

    def kind_pods(self) -> Result:
        if not self.kind_state().running:
            return Result(SKIP, "cluster not running")
        res = run(
            [
                "kubectl",
                "--context",
                f"kind-{self.cluster}",
                "-n",
                "p2",
                "get",
                "pods",
                "-o",
                "json",
            ],
            30,
        )
        if res is None or res.returncode != 0:
            return Result(FAIL, "kubectl get pods failed")
        bad, ok = [], 0
        for pod in json.loads(res.stdout)["items"]:
            phase = pod["status"].get("phase")
            ready = all(c.get("ready") for c in pod["status"].get("containerStatuses", []))
            if phase == "Succeeded" or (phase == "Running" and ready):
                ok += 1
            else:
                bad.append(f"{pod['metadata']['name']} {phase}")
        if not ok and not bad:
            return Result(FAIL, "no app pods: the chart isn't deployed (make kind-redeploy)")
        detail = f"{ok} pods ready" + (f"; not ready: {', '.join(bad)}" if bad else "")
        return Result(FAIL if bad else PASS, detail)

    def kind_gateway(self) -> Result:
        if not self.kind_state().running:
            return Result(SKIP, "cluster not running")
        host = {"Host": "app.localhost"}
        web = self.http.get("http://127.0.0.1/", headers=host)
        api = self.http.get("http://127.0.0.1/api/health", headers=host)
        # By IP (Python can't resolve *.localhost), so name the host for TLS too: without SNI,
        # Envoy has no certificate to pick and drops the connection.
        with httpx.Client(verify=False, timeout=15) as insecure:  # the local CA isn't trusted here
            tls = insecure.get(
                "https://127.0.0.1/api/health",
                headers=host,
                extensions={"sni_hostname": "app.localhost"},
            )
        ok = web.status_code == api.status_code == tls.status_code == 200
        codes = f"/ {web.status_code}, /api/health {api.status_code}, https {tls.status_code}"
        return Result(PASS if ok else FAIL, f"app.localhost: {codes}")

    def kind_image(self) -> Result:
        if not self.kind_state().running:
            return Result(SKIP, "cluster not running")
        res = run(
            [
                "kubectl",
                "--context",
                f"kind-{self.cluster}",
                "-n",
                "p2",
                "get",
                "deploy",
                "api",
                "-o",
                "jsonpath={.spec.template.spec.containers[0].image}",
            ],
            20,
        )
        if res is None or res.returncode != 0 or ":" not in res.stdout:
            return Result(FAIL, "no api Deployment: the chart isn't deployed (make kind-redeploy)")
        deployed = res.stdout.rsplit(":", 1)[-1]
        current = image_tag(ROOT)
        if deployed == current:
            return Result(PASS, f"runs the current code ({current})")
        return Result(WARN, f"runs {deployed}; working tree is {current} (make kind-redeploy)")

    # ---- the list ---------------------------------------------------------------------------

    def checks(self) -> Iterator[tuple[str, str, Check]]:
        yield "APP", "web /", self.web_home
        yield "APP", "web /sign-in", self.web_sign_in
        yield "APP", "api /health", self.api_health
        yield "APP", "api /openapi.json", self.api_docs
        yield "APP", "api /metrics", self.api_metrics
        yield "APP", "api fails closed", self.api_auth
        yield "DATA STORES", "qdrant catalog", self.qdrant
        yield "DATA STORES", "qdrant api key", self.qdrant_auth
        yield "DATA STORES", "dynamodb local", self.dynamodb
        yield "DATA STORES", "redis (app)", self.redis_app
        yield "OBSERVABILITY", "prometheus targets", self.prometheus_targets
        yield "OBSERVABILITY", "blackbox probes", self.prometheus_probes
        yield "OBSERVABILITY", "alert rules", self.prometheus_rules
        yield "OBSERVABILITY", "grafana dashboards", self.grafana
        yield "OBSERVABILITY", "grafana datasources", self.grafana_datasources
        yield "OBSERVABILITY", "grafana panel data", self.grafana_panels
        yield "OBSERVABILITY", "jaeger traces", self.jaeger
        yield "OBSERVABILITY", "langfuse health", self.langfuse
        yield "OBSERVABILITY", "langfuse auto-login", self.langfuse_autologin
        yield "OBSERVABILITY", "langfuse traces", self.langfuse_traces
        yield "OBSERVABILITY", "redisinsight", self.redisinsight
        yield "OBSERVABILITY", "cadvisor", self.cadvisor
        yield "LANGFUSE STORES", "postgres", self.postgres
        yield "LANGFUSE STORES", "clickhouse", self.clickhouse
        yield "LANGFUSE STORES", "redis (langfuse)", self.redis_langfuse
        yield "LANGFUSE STORES", "minio", self.minio
        yield "LLM", "groq", self.provider("Groq", "GROQ_API_KEY", self.groq)
        yield "LLM", "openai chat", self.provider("OpenAI", "OPENAI_API_KEY", self.openai)
        yield "LLM", "openai embeddings", self.provider("OpenAI", "OPENAI_API_KEY", self.embeddings)
        yield "LLM", "anthropic", self.provider("Anthropic", "ANTHROPIC_API_KEY", self.anthropic)
        yield "LLM", "serpapi account", self.provider("SerpApi", "SERPAPI_API_KEY", self.serpapi)
        yield "LLM", "provider metrics", self.llm_provider_metrics
        yield "KUBERNETES", "kind nodes", self.kind_nodes
        yield "KUBERNETES", "kind pods", self.kind_pods
        yield "KUBERNETES", "kind gateway", self.kind_gateway
        yield "KUBERNETES", "kind image", self.kind_image

    def run(self) -> dict[str, int]:
        counts = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0}
        group = ""
        for section, name, check in self.checks():
            if section != group:
                group = section
                print(f"\n  {section}")
            try:
                result = check()
            except Exception as exc:  # a check that can't even run is a failure, said plainly
                result = Result(FAIL, f"{type(exc).__name__}: {exc}")
            counts[result.status] += 1
            print(f"    {result.status}  {name:<22} {self.redact(result.detail)}", flush=True)
        return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--cluster", default="p2")
    parser.add_argument("--live", action="store_true", help="one tiny call per LLM provider")
    args = parser.parse_args(argv)
    started = time.monotonic()
    print(
        "\n  P2 verify" + (" (LIVE: calls each LLM provider once)" if args.live else " (read-only)")
    )
    counts = Verifier(load_env(), args.cluster, args.live).run()
    print(
        f"\n  {counts[PASS]} PASS, {counts[WARN]} WARN, {counts[FAIL]} FAIL, {counts[SKIP]} SKIP"
        f"  in {time.monotonic() - started:.0f}s\n"
    )
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
