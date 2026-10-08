"""Generate the P2 Grafana dashboards: `uv run python ops/observability/grafana/build_dashboards.py`.

    p2-api-llm        (shared: ops/helm/p2-recommender/files/dashboards; Kubernetes loads it too)
                      traffic, latency, errors, LLM calls/latency/tokens/failover, cache, process
    p2-health         (compose; Grafana's home page) every service up/down, alerts, headline numbers
    p2-data-stores    (compose) Redis x2, Qdrant, Postgres, ClickHouse, MinIO, DynamoDB-local
    p2-containers     (compose) memory, CPU and network per container (cAdvisor)

Every query here is checked against the live Prometheus by `make verify` (panels must return
data, except event counters that are legitimately empty until the event happens).
The hand-made p2-overview dashboard (product KPIs) is kept as it is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "ops" / "helm" / "p2-recommender" / "files" / "dashboards"
COMPOSE = ROOT / "ops" / "observability" / "grafana" / "dashboards"
DS = {"type": "prometheus", "uid": "prometheus"}

# Panels whose metric only exists once the event has happened (a counter with labels has no
# series until its first increment). `make verify` accepts "no data" for these and only these.
EVENT_PANELS = {
    "Degraded answers by reason (source unavailable)",
    "Guardrail blocks and no-match answers",
    "OOM kills (1h)",
}

UP_DOWN = [
    {
        "type": "value",
        "options": {
            "0": {"text": "DOWN", "color": "red", "index": 0},
            "1": {"text": "UP", "color": "green", "index": 1},
        },
    }
]

# Short service names for probe and target tiles: http://api:2011/health -> api
SERVICE = '"service", "$1", "instance", "(?:https?://)?([^:/]+).*"'


def svc(expr: str) -> str:
    return f"label_replace({expr}, {SERVICE})"


@dataclass
class Target:
    expr: str
    legend: str = ""
    instant: bool = False
    fmt: str = "time_series"


@dataclass
class Dashboard:
    uid: str
    title: str
    description: str
    shared: bool = False
    panels: list[dict[str, Any]] = field(default_factory=list)
    _x: int = 0
    _y: int = 0
    _row_h: int = 0
    _id: int = 0

    def row(self, title: str) -> None:
        self._newline()
        self._id += 1
        self.panels.append(
            {
                "type": "row",
                "title": title,
                "id": self._id,
                "collapsed": False,
                "gridPos": {"x": 0, "y": self._y, "w": 24, "h": 1},
                "panels": [],
            }
        )
        self._y += 1

    def _newline(self) -> None:
        if self._x:
            self._y += self._row_h
            self._x, self._row_h = 0, 0

    def _place(self, w: int, h: int) -> dict[str, int]:
        if self._x + w > 24:
            self._newline()
        pos = {"x": self._x, "y": self._y, "w": w, "h": h}
        self._x += w
        self._row_h = max(self._row_h, h)
        return pos

    def _panel(
        self,
        kind: str,
        title: str,
        targets: list[Target],
        w: int,
        h: int,
        description: str,
        field_config: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        self._id += 1
        self.panels.append(
            {
                "type": kind,
                "title": title,
                "id": self._id,
                "description": description,
                "datasource": DS,
                "gridPos": self._place(w, h),
                "targets": [
                    {
                        "refId": chr(65 + i),
                        "datasource": DS,
                        "expr": t.expr,
                        "legendFormat": t.legend,
                        "instant": t.instant,
                        "range": not t.instant,
                        "format": t.fmt,
                    }
                    for i, t in enumerate(targets)
                ],
                "fieldConfig": {"defaults": field_config, "overrides": []},
                "options": options,
            }
        )

    def timeseries(
        self,
        title: str,
        *targets: Target,
        unit: str = "short",
        w: int = 12,
        h: int = 8,
        description: str = "",
        stack: bool = False,
        max_: float | None = None,
    ) -> None:
        custom: dict[str, Any] = {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 12,
            "showPoints": "never",
            "spanNulls": True,
        }
        if stack:
            custom["stacking"] = {"mode": "normal", "group": "A"}
        defaults: dict[str, Any] = {"unit": unit, "custom": custom, "min": 0}
        if max_ is not None:
            defaults["max"] = max_
        self._panel(
            "timeseries",
            title,
            list(targets),
            w,
            h,
            description,
            defaults,
            {
                "legend": {
                    "displayMode": "table",
                    "placement": "right",
                    "calcs": ["lastNotNull", "max"],
                },
                "tooltip": {"mode": "multi", "sort": "desc"},
            },
        )

    def stat(
        self,
        title: str,
        *targets: Target,
        unit: str = "short",
        w: int = 4,
        h: int = 4,
        description: str = "",
        thresholds: list[tuple[float | None, str]] | None = None,
        mappings: list[dict[str, Any]] | None = None,
        text_mode: str = "auto",
        color_mode: str = "background",
        decimals: int | None = None,
    ) -> None:
        steps = [{"value": v, "color": c} for v, c in (thresholds or [(None, "blue")])]
        defaults: dict[str, Any] = {
            "unit": unit,
            "thresholds": {"mode": "absolute", "steps": steps},
            "mappings": mappings or [],
            "color": {"mode": "thresholds"},
        }
        if decimals is not None:
            defaults["decimals"] = decimals
        self._panel(
            "stat",
            title,
            list(targets),
            w,
            h,
            description,
            defaults,
            {
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "colorMode": color_mode,
                "graphMode": "none",
                "textMode": text_mode,
                "justifyMode": "auto",
                "orientation": "auto",
                "wideLayout": True,
            },
        )

    def table(
        self,
        title: str,
        target: Target,
        w: int = 24,
        h: int = 7,
        description: str = "",
        hide: list[str] | None = None,
    ) -> None:
        self._panel(
            "table",
            title,
            [target],
            w,
            h,
            description,
            {"unit": "short"},
            {"showHeader": True, "cellHeight": "sm"},
        )
        self.panels[-1]["transformations"] = [
            {"id": "organize", "options": {"excludeByName": {k: True for k in (hide or [])}}}
        ]

    def to_json(self, links: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "title": self.title,
            "description": self.description,
            "tags": ["p2"],
            "timezone": "browser",
            "schemaVersion": 39,
            "version": 1,
            "editable": False,
            "graphTooltip": 1,
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "links": links,
            "panels": self.panels,
            "templating": {"list": []},
            "annotations": {"list": []},
        }


def api_llm() -> Dashboard:
    d = Dashboard(
        "p2-api-llm",
        "P2 - API & LLM",
        "Request traffic, latency and errors per endpoint; every LLM call per provider "
        "(latency, tokens, failover); cache effectiveness; the API process.",
        shared=True,
    )
    d.row("Traffic: rate, errors, latency")
    d.timeseries(
        "Requests/s by endpoint",
        Target("sum by (path) (rate(http_requests_total[5m]))", "{{path}}"),
        unit="reqps",
    )
    d.timeseries(
        "Responses/s by status",
        Target("sum by (status) (rate(http_requests_total[5m]))", "{{status}}"),
        unit="reqps",
    )
    d.timeseries(
        "Latency by endpoint (p50 / p95 / p99)",
        *[
            Target(
                f"histogram_quantile({q}, sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))",
                f"p{int(float(q) * 100)} {{{{path}}}}",
            )
            for q in ("0.5", "0.95", "0.99")
        ],
        unit="s",
    )
    d.timeseries(
        "Server errors (5xx) % of requests",
        Target(
            '100 * (sum(rate(http_requests_total{status=~"5.."}[5m])) or vector(0)) / clamp_min(sum(rate(http_requests_total[5m])), 1e-9)',
            "5xx %",
        ),
        unit="percent",
        description="Above 1% for 5 minutes fires HighErrorRate.",
    )
    d.timeseries(
        "Refusals: 401 unauthenticated, 429 rate-limited",
        Target(
            'sum(rate(http_requests_total{status="401"}[5m])) or vector(0)', "401 unauthenticated"
        ),
        Target('sum(rate(http_requests_total{status="429"}[5m])) or vector(0)', "429 rate-limited"),
        unit="reqps",
        description="Auth fails closed (401) and per-user limits (429) working, not outages.",
    )
    d.row("LLM: every call, per provider (Groq -> OpenAI -> Anthropic)")
    d.timeseries(
        "LLM calls/s by provider and outcome",
        Target(
            "sum by (provider, status) (rate(llm_requests_total[5m]))", "{{provider}} {{status}}"
        ),
        unit="reqps",
        description="An error on one provider followed by 'ok' on the next is a failover.",
    )
    d.stat(
        "LLM failure % by provider (15m)",
        Target(
            '100 * sum by (provider) (increase(llm_requests_total{status="error"}[15m])) / clamp_min(sum by (provider) (increase(llm_requests_total[15m])), 1e-9)',
            "{{provider}}",
        ),
        unit="percent",
        w=6,
        h=8,
        thresholds=[(None, "green"), (5, "orange"), (50, "red")],
        description="Above 50% (3+ calls) for 5 minutes fires LLMProviderFailing.",
    )
    d.timeseries(
        "LLM latency by provider (p50 / p95)",
        *[
            Target(
                f"histogram_quantile({q}, sum by (le, provider) (rate(llm_request_duration_seconds_bucket[5m])))",
                f"p{int(float(q) * 100)} {{{{provider}}}}",
            )
            for q in ("0.5", "0.95")
        ],
        unit="s",
        w=6,
    )
    d.timeseries(
        "Tokens/min by provider and direction",
        Target(
            "60 * sum by (provider, type) (rate(llm_tokens_total[5m]))", "{{provider}} {{type}}"
        ),
        w=12,
    )
    d.stat(
        "Tokens in the last 24h",
        Target(
            "sum by (provider, type) (increase(llm_tokens_total[24h]))", "{{provider}} {{type}}"
        ),
        w=12,
        h=8,
        decimals=0,
        color_mode="value",
    )
    d.row("Cache and live shopping source")
    d.timeseries(
        "Cache hit ratio by layer",
        Target(
            "sum by (layer) (rate(cache_hits_total[15m])) / clamp_min(sum by (layer) (rate(cache_hits_total[15m])) + sum by (layer) (rate(cache_misses_total[15m])), 1e-9)",
            "{{layer}}",
        ),
        unit="percentunit",
        max_=1,
        description="Every aggregate miss spends a metered SerpApi search.",
    )
    d.timeseries(
        "Cache hits and misses/s",
        Target("sum by (layer) (rate(cache_hits_total[5m]))", "hit {{layer}}"),
        Target("sum by (layer) (rate(cache_misses_total[5m]))", "miss {{layer}}"),
        unit="ops",
    )
    d.stat(
        "SerpApi searches (24h; free plan 250/month)",
        Target("sum(increase(serpapi_searches_total[24h])) or vector(0)", "searches"),
        w=6,
        h=6,
        decimals=0,
        thresholds=[(None, "green"), (20, "orange"), (30, "red")],
    )
    d.timeseries(
        "Degraded answers by reason (source unavailable)",
        Target("sum by (reason) (increase(source_unavailable_total[1h]))", "{{reason}}"),
        w=9,
        h=6,
    )
    d.timeseries(
        "Guardrail blocks and no-match answers",
        Target("sum by (kind) (increase(guardrail_blocks_total[1h]))", "guardrail {{kind}}"),
        Target("sum(increase(no_match_total[1h]))", "no match"),
        w=9,
        h=6,
    )
    d.row("API process")
    d.timeseries(
        "CPU (cores)",
        Target('rate(process_cpu_seconds_total{job="p2-api"}[5m])', "{{instance}}"),
        w=6,
    )
    d.timeseries(
        "Memory (RSS)",
        Target('process_resident_memory_bytes{job="p2-api"}', "{{instance}}"),
        unit="bytes",
        w=6,
    )
    d.timeseries(
        "Open file descriptors", Target('process_open_fds{job="p2-api"}', "{{instance}}"), w=6
    )
    d.timeseries(
        "Python GC collections/s",
        Target(
            'sum by (generation) (rate(python_gc_collections_total{job="p2-api"}[5m]))',
            "gen {{generation}}",
        ),
        w=6,
    )
    return d


def health() -> Dashboard:
    d = Dashboard(
        "p2-health",
        "P2 - Service health",
        "Is every component up, is anything alerting, and the headline numbers. "
        "Grafana's home page.",
    )
    d.row("Is every service answering? (blackbox probes, every 15s)")
    d.stat(
        "Services",
        Target(svc("probe_success"), "{{service}}"),
        w=24,
        h=6,
        mappings=UP_DOWN,
        thresholds=[(None, "red"), (1, "green")],
        text_mode="value_and_name",
        description="HTTP health endpoints and TCP connects, probed from inside the network.",
    )
    d.stat(
        "Metrics endpoints scraped",
        Target("up", "{{job}}"),
        w=24,
        h=5,
        mappings=UP_DOWN,
        thresholds=[(None, "red"), (1, "green")],
        text_mode="value_and_name",
    )
    d.row("Headline numbers")
    d.stat(
        "Firing alerts",
        Target('count(ALERTS{alertstate="firing"}) or vector(0)', "firing"),
        w=4,
        thresholds=[(None, "green"), (1, "red")],
    )
    d.stat(
        "API requests/s",
        Target("sum(rate(http_requests_total[5m])) or vector(0)", "req/s"),
        unit="reqps",
        w=4,
        decimals=2,
    )
    d.stat(
        "API 5xx %",
        Target(
            '100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(http_requests_total[5m])), 1e-9) or vector(0)',
            "5xx",
        ),
        unit="percent",
        w=4,
        thresholds=[(None, "green"), (1, "red")],
    )
    d.stat(
        "API p95 latency",
        Target(
            "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[15m])))",
            "p95",
        ),
        unit="s",
        w=4,
        thresholds=[(None, "green"), (2, "orange"), (4, "red")],
    )
    d.stat(
        "SerpApi searches (24h)",
        Target("sum(increase(serpapi_searches_total[24h])) or vector(0)", "24h"),
        w=4,
        decimals=0,
        thresholds=[(None, "green"), (20, "orange"), (30, "red")],
    )
    d.stat(
        "Stack memory",
        Target(
            'sum(max by (container_label_com_docker_compose_service) (container_memory_working_set_bytes{container_label_com_docker_compose_project="p2-recommender"}))',
            "stack",
        ),
        unit="bytes",
        w=4,
        thresholds=[(None, "green"), (8e9, "orange"), (10e9, "red")],
    )
    d.stat(
        "LLM failure % by provider (15m)",
        Target(
            '100 * sum by (provider) (increase(llm_requests_total{status="error"}[15m])) / clamp_min(sum by (provider) (increase(llm_requests_total[15m])), 1e-9)',
            "{{provider}}",
        ),
        unit="percent",
        w=12,
        thresholds=[(None, "green"), (5, "orange"), (50, "red")],
        text_mode="value_and_name",
    )
    d.stat(
        "LLM calls by provider (1h)",
        Target("sum by (provider) (increase(llm_requests_total[1h]))", "{{provider}}"),
        w=12,
        decimals=0,
        color_mode="value",
        text_mode="value_and_name",
    )
    d.row("Alerts and probe latency")
    d.table(
        "Alerts (pending and firing)",
        Target("ALERTS", instant=True, fmt="table"),
        w=12,
        h=8,
        hide=["Time", "__name__", "Value"],
    )
    d.timeseries(
        "Probe response time",
        Target(svc("probe_duration_seconds"), "{{service}}"),
        unit="s",
        w=12,
        h=8,
    )
    return d


def data_stores() -> Dashboard:
    d = Dashboard(
        "p2-data-stores",
        "P2 - Data stores",
        "Redis (app cache and Langfuse queue), Qdrant, the Langfuse Postgres, ClickHouse and "
        "MinIO, and DynamoDB-local.",
    )
    d.row("Redis: app cache (app-redis) and Langfuse queue (langfuse-redis)")
    d.timeseries(
        "Memory used", Target("redis_memory_used_bytes", "{{instance}}"), unit="bytes", w=8
    )
    d.timeseries(
        "Commands/s",
        Target("rate(redis_commands_processed_total[5m])", "{{instance}}"),
        unit="ops",
        w=8,
    )
    d.timeseries(
        "Keyspace hit ratio",
        Target(
            "rate(redis_keyspace_hits_total[15m]) / clamp_min(rate(redis_keyspace_hits_total[15m]) + rate(redis_keyspace_misses_total[15m]), 1e-9)",
            "{{instance}}",
        ),
        unit="percentunit",
        max_=1,
        w=8,
    )
    d.stat(
        "Keys",
        Target("sum by (instance) (redis_db_keys)", "{{instance}}"),
        w=8,
        h=5,
        color_mode="value",
        text_mode="value_and_name",
    )
    d.timeseries("Connected clients", Target("redis_connected_clients", "{{instance}}"), w=8, h=5)
    d.timeseries(
        "Expired and evicted keys/s",
        Target("rate(redis_expired_keys_total[5m])", "expired {{instance}}"),
        Target("rate(redis_evicted_keys_total[5m])", "evicted {{instance}}"),
        w=8,
        h=5,
    )
    d.row("Qdrant: product vectors")
    d.stat("Collections", Target("collections_total", "collections"), w=4, color_mode="value")
    d.stat("Vectors", Target("collections_vector_total", "vectors"), w=4, color_mode="value")
    d.timeseries(
        "REST calls/s by endpoint",
        Target(
            "sum by (endpoint, method) (rate(rest_responses_total[5m]))", "{{method}} {{endpoint}}"
        ),
        unit="reqps",
        w=8,
        h=8,
    )
    d.timeseries(
        "REST latency by endpoint (avg)",
        Target("rest_responses_avg_duration_seconds", "{{method}} {{endpoint}}"),
        unit="s",
        w=8,
        h=8,
    )
    d.timeseries(
        "Qdrant memory (resident)",
        Target("memory_resident_bytes", "resident"),
        unit="bytes",
        w=8,
        h=4,
    )
    d.row("Postgres: Langfuse metadata")
    d.stat(
        "Postgres",
        Target("pg_up", "pg_up"),
        w=4,
        mappings=UP_DOWN,
        thresholds=[(None, "red"), (1, "green")],
    )
    d.stat(
        "Database size",
        Target('pg_database_size_bytes{datname="langfuse"}', "langfuse"),
        unit="bytes",
        w=4,
        color_mode="value",
    )
    d.timeseries(
        "Connections",
        Target('pg_stat_database_numbackends{datname="langfuse"}', "connections"),
        w=8,
    )
    d.timeseries(
        "Transactions/s",
        Target('rate(pg_stat_database_xact_commit{datname="langfuse"}[5m])', "commit"),
        Target('rate(pg_stat_database_xact_rollback{datname="langfuse"}[5m])', "rollback"),
        unit="ops",
        w=8,
    )
    d.row("ClickHouse: Langfuse traces")
    d.timeseries(
        "Rows inserted/s",
        Target("rate(ClickHouseProfileEvents_InsertedRows[5m])", "rows"),
        unit="rowsps",
        w=8,
    )
    d.timeseries(
        "Queries/s", Target("rate(ClickHouseProfileEvents_Query[5m])", "queries"), unit="ops", w=8
    )
    d.timeseries(
        "Memory tracked", Target("ClickHouseMetrics_MemoryTracking", "memory"), unit="bytes", w=8
    )
    d.row("MinIO: Langfuse event and media blobs")
    d.stat(
        "Objects", Target("minio_cluster_usage_object_total", "objects"), w=4, color_mode="value"
    )
    d.stat("Buckets", Target("minio_cluster_bucket_total", "buckets"), w=4, color_mode="value")
    d.stat(
        "Usable free",
        Target("minio_cluster_capacity_usable_free_bytes", "free"),
        unit="bytes",
        w=4,
        color_mode="value",
    )
    d.timeseries(
        "S3 requests/s by API",
        Target("sum by (api) (rate(minio_s3_requests_total[5m]))", "{{api}}"),
        unit="reqps",
        w=12,
        h=4,
    )
    d.row("DynamoDB-local: chat history (no metrics endpoint: TCP probe only)")
    d.stat(
        "DynamoDB-local",
        Target('probe_success{instance="dynamodb:8000"}', "dynamodb"),
        w=6,
        mappings=UP_DOWN,
        thresholds=[(None, "red"), (1, "green")],
    )
    d.timeseries(
        "Connect time",
        Target('probe_duration_seconds{instance="dynamodb:8000"}', "connect"),
        unit="s",
        w=18,
        h=4,
    )
    return d


def containers() -> Dashboard:
    d = Dashboard(
        "p2-containers",
        "P2 - Containers",
        "Memory, CPU and network for every container in the stack (cAdvisor).",
    )
    by = "container_label_com_docker_compose_service"
    sel = '{container_label_com_docker_compose_project="p2-recommender"}'
    d.stat(
        "Docker VM memory",
        Target("max(machine_memory_bytes)", "VM"),
        unit="bytes",
        w=6,
        color_mode="value",
    )
    d.stat(
        "Stack memory (working set)",
        Target(f"sum(max by ({by}) (container_memory_working_set_bytes{sel}))", "stack"),
        unit="bytes",
        w=6,
        thresholds=[(None, "green"), (8e9, "orange"), (10e9, "red")],
    )
    d.stat(
        "Containers reporting",
        Target(f"count(count by ({by}) (container_memory_working_set_bytes{sel}))", "containers"),
        w=6,
        color_mode="value",
    )
    d.stat(
        "Stack CPU (cores)",
        Target(f"sum(max by ({by}) (rate(container_cpu_usage_seconds_total{sel}[5m])))", "cores"),
        w=6,
        color_mode="value",
        decimals=2,
    )
    d.timeseries(
        "Memory by service",
        Target(f"max by ({by}) (container_memory_working_set_bytes{sel})", f"{{{{{by}}}}}"),
        unit="bytes",
        w=24,
        h=10,
        stack=True,
    )
    d.timeseries(
        "CPU by service (cores)",
        Target(
            f"max by ({by}) (rate(container_cpu_usage_seconds_total{sel}[5m]))", f"{{{{{by}}}}}"
        ),
        w=12,
        h=9,
    )
    d.timeseries(
        "Network received by service",
        Target(
            f"max by ({by}) (rate(container_network_receive_bytes_total{sel}[5m]))", f"{{{{{by}}}}}"
        ),
        unit="Bps",
        w=12,
        h=9,
    )
    d.timeseries(
        "Network sent by service",
        Target(
            f"max by ({by}) (rate(container_network_transmit_bytes_total{sel}[5m]))",
            f"{{{{{by}}}}}",
        ),
        unit="Bps",
        w=12,
        h=9,
    )
    d.timeseries(
        "OOM kills (1h)",
        Target(
            f"max by ({by}) (increase(container_oom_events_total{sel}[1h])) > 0", f"{{{{{by}}}}}"
        ),
        w=12,
        h=9,
    )
    return d


LINKS = [
    {
        "title": "P2 dashboards",
        "type": "dashboards",
        "tags": ["p2"],
        "asDropdown": True,
        "includeVars": False,
        "keepTime": True,
    },
    {
        "title": "Langfuse (signed in)",
        "type": "link",
        "url": "http://localhost:2008",
        "targetBlank": True,
    },
    {"title": "Jaeger", "type": "link", "url": "http://localhost:2006", "targetBlank": True},
    {
        "title": "Prometheus",
        "type": "link",
        "url": "http://localhost:2009/targets",
        "targetBlank": True,
    },
    {"title": "RedisInsight", "type": "link", "url": "http://localhost:2005", "targetBlank": True},
    {"title": "Web app", "type": "link", "url": "http://localhost:2012", "targetBlank": True},
]


def build() -> list[tuple[Path, dict[str, Any]]]:
    out = []
    for dash in (api_llm(), health(), data_stores(), containers()):
        folder = SHARED if dash.shared else COMPOSE
        # Shared dashboards also load in Kubernetes, where the localhost links would be wrong.
        links = LINKS[:1] if dash.shared else LINKS
        out.append((folder / f"{dash.uid}.json", dash.to_json(links)))
    return out


def main() -> int:
    COMPOSE.mkdir(parents=True, exist_ok=True)
    for path, payload in build():
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        panels = sum(1 for p in payload["panels"] if p["type"] != "row")
        print(f"wrote {path.relative_to(ROOT)} ({panels} panels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
