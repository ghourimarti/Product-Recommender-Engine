"""Generate the P2 Grafana dashboards: `uv run python ops/observability/grafana/build_dashboards.py`.

Every dashboard reads top-down as a list of questions. Each numbered section can be collapsed,
and so can its sub-sections ("1 — Is every service answering?" > "1.1 — Services"):

    p2-health        home page: is everything up, is anything firing, is there room to run
    p2-api-llm       traffic, latency, errors, every LLM call per provider, cache, the API process
    p2-data-stores   Qdrant, Redis x2, Postgres, ClickHouse, MinIO, DynamoDB-local
    p2-containers    the Docker VM, every container, and the monitoring stack itself

Two output formats from one definition:
  - compose runs Grafana 13: v2 dashboards (nested, collapsible rows) in
    ops/observability/grafana/dashboards
  - Kubernetes runs Grafana 12 (kube-prometheus-stack): p2-api-llm in the classic format, sections
    flattened into plain rows, in ops/helm/p2-recommender/files/dashboards (the chart's ConfigMap)

`make verify` runs every query against the live Prometheus: each must return data, except panels
marked idle_ok, which are legitimately empty while nothing happens (no OOM kill, no fallback to
OpenAI because Groq answered everything, no Qdrant search in the window).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "ops" / "helm" / "p2-recommender" / "files" / "dashboards"
COMPOSE = ROOT / "ops" / "observability" / "grafana" / "dashboards"
DS_UID = "prometheus"

UP_DOWN = [
    {
        "type": "value",
        "options": {
            "0": {"text": "DOWN", "color": "red", "index": 0},
            "1": {"text": "UP", "color": "green", "index": 1},
        },
    }
]
Steps = Sequence[tuple[float | None, str]]
RED_GREEN: Steps = [(None, "red"), (1, "green")]
OK_FAILED = [
    {
        "type": "value",
        "options": {
            "0": {"text": "FAILED", "color": "red", "index": 0},
            "1": {"text": "OK", "color": "green", "index": 1},
        },
    }
]

# Short names for probe and target tiles: http://api:2011/health -> api, langfuse-redis -> redis
SERVICE = '"service", "$1", "instance", "(?:https?://)?([^:/]+).*"'
SHORT = '"service", "$1", "instance", "(?:https?://)?(?:langfuse-)?([^:/]+).*"'
P2 = '{container_label_com_docker_compose_project="p2-recommender"}'
BY_SERVICE = "container_label_com_docker_compose_service"


def svc(expr: str, short: bool = False) -> str:
    return f"label_replace({expr}, {SHORT if short else SERVICE})"


# ---- the model ----------------------------------------------------------------------------


@dataclass
class Target:
    expr: str
    legend: str = ""
    instant: bool = False
    fmt: str = "time_series"


@dataclass
class Panel:
    kind: str
    title: str
    targets: list[Target]
    w: int
    h: int
    description: str
    defaults: dict[str, Any]
    options: dict[str, Any]
    overrides: list[dict[str, Any]] = field(default_factory=list)
    transformations: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    idle_ok: bool = False  # empty while nothing happens: not a broken query


@dataclass
class Section:
    title: str
    children: list[Panel | Section]
    collapsed: bool = False


@dataclass
class Dashboard:
    uid: str
    title: str
    description: str
    sections: list[Section]
    shared: bool = False  # also exported in the classic format for Kubernetes


# ---- panel factories ----------------------------------------------------------------------


def _steps(thresholds: Steps | None) -> dict[str, Any]:
    pairs = thresholds or [(None, "blue")]
    return {"mode": "absolute", "steps": [{"value": v, "color": c} for v, c in pairs]}


def kpi(
    title: str,
    target: Target,
    *,
    unit: str = "short",
    description: str,
    thresholds: Steps | None = None,
    decimals: int | None = None,
    w: int = 3,
    h: int = 4,
    no_value: str = "0",
    idle_ok: bool = False,
    mappings: list[dict[str, Any]] | None = None,
    spark: bool = True,
) -> Panel:
    """A headline number with a sparkline, coloured by its thresholds."""
    defaults: dict[str, Any] = {
        "unit": unit,
        "thresholds": _steps(thresholds),
        "color": {"mode": "thresholds"},
        "noValue": no_value,
        "mappings": mappings or [],
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    return Panel(
        "stat",
        title,
        [target],
        w,
        h,
        description,
        defaults,
        {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "value",
            "graphMode": "area" if spark else "none",
            "textMode": "value",
            "justifyMode": "center",
            "orientation": "auto",
            "wideLayout": True,
            "showPercentChange": False,
        },
        idle_ok=idle_ok,
    )


def tiles(
    title: str,
    target: Target,
    *,
    w: int,
    h: int = 4,
    description: str,
    mappings: list[dict[str, Any]] | None = None,
    thresholds: Steps | None = None,
    unit: str = "short",
    decimals: int | None = None,
) -> Panel:
    """One small coloured tile per series (UP/DOWN by default)."""
    defaults: dict[str, Any] = {
        "unit": unit,
        "thresholds": _steps(thresholds or RED_GREEN),
        "mappings": UP_DOWN if mappings is None else mappings,
        "color": {"mode": "thresholds"},
        "noValue": "none",
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    return Panel(
        "stat",
        title,
        [target],
        w,
        h,
        description,
        defaults,
        {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "background",
            "graphMode": "none",
            "textMode": "value_and_name",
            "justifyMode": "center",
            "orientation": "vertical",
            "wideLayout": True,
            "text": {"titleSize": 12, "valueSize": 16},
            "showPercentChange": False,
        },
    )


def ts(
    title: str,
    *targets: Target,
    unit: str = "short",
    w: int = 12,
    h: int = 9,
    description: str,
    stack: bool = False,
    max_: float | None = None,
    line: float | None = None,  # a dashed target line (an NFR or a limit)
    bars: bool = False,
    idle: str = "",  # set = may be empty while idle; this text shows instead of "No data"
    legend: str = "bottom",  # "right" for panels with many series
) -> Panel:
    """A time series with a gradient fill and a table legend (last, mean, max)."""
    custom: dict[str, Any] = {
        "drawStyle": "bars" if bars else "line",
        "lineWidth": 2,
        "fillOpacity": 70 if bars else 18,
        "gradientMode": "opacity",
        "lineInterpolation": "smooth",
        "showPoints": "never",
        "spanNulls": True,
        "axisBorderShow": False,
        "axisCenteredZero": False,
        "barAlignment": 0,
        "thresholdsStyle": {"mode": "dashed" if line is not None else "off"},
    }
    if stack:
        custom["stacking"] = {"mode": "normal", "group": "A"}
    if line is not None:
        custom["axisSoftMax"] = line * 1.15  # keep the target line on screen
    defaults: dict[str, Any] = {
        "unit": unit,
        "custom": custom,
        "min": 0,
        "color": {"mode": "palette-classic"},
        "thresholds": _steps([(None, "transparent"), (line, "red")] if line is not None else None),
    }
    if max_ is not None:
        defaults["max"] = max_
    if idle:
        defaults["noValue"] = idle
    return Panel(
        "timeseries",
        title,
        list(targets),
        w,
        h,
        description,
        defaults,
        {
            "legend": {
                "showLegend": True,
                "displayMode": "table",
                "placement": legend,
                # Narrow panels and right-hand legends have room for two columns, not three.
                "calcs": ["lastNotNull", "max"]
                if legend == "right" or w <= 6
                else ["lastNotNull", "mean", "max"],
                "sortBy": "Last *",
                "sortDesc": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        idle_ok=bool(idle),
    )


def bars(
    title: str,
    target: Target,
    *,
    unit: str = "short",
    w: int = 12,
    h: int = 8,
    description: str,
    thresholds: Steps | None = None,
    max_: float | None = None,
) -> Panel:
    """Horizontal bars, one per series, biggest first: who is using the most right now."""
    target = Target(target.expr, target.legend, instant=True)
    defaults: dict[str, Any] = {
        "unit": unit,
        "thresholds": _steps(thresholds or [(None, "#5794F2")]),
        "color": {"mode": "thresholds"}
        if thresholds
        else {"mode": "fixed", "fixedColor": "#5794F2"},
        "min": 0,
    }
    if max_ is not None:
        defaults["max"] = max_
    return Panel(
        "bargauge",
        title,
        [target],
        w,
        h,
        description,
        defaults,
        {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "horizontal",
            "displayMode": "basic",
            "valueMode": "text",
            "namePlacement": "left",
            "showUnfilled": True,
            "sizing": "manual",
            "minVizHeight": 14,
            "maxVizHeight": 18,
            "text": {"titleSize": 12, "valueSize": 12},
        },
        transformations=[{"id": "sortBy", "options": {"sort": [{"field": "Value", "desc": True}]}}],
    )


def heatmap(title: str, expr: str, *, w: int = 12, h: int = 8, description: str) -> Panel:
    return Panel(
        "heatmap",
        title,
        [Target(expr, "{{le}}", fmt="heatmap")],
        w,
        h,
        description,
        {"unit": "short"},
        {
            "calculate": False,
            "cellGap": 1,
            "color": {"mode": "scheme", "scheme": "Oranges", "steps": 64, "exponent": 0.5},
            "yAxis": {"unit": "s", "axisPlacement": "left"},
            "rowsFrame": {"layout": "auto"},
            "legend": {"show": True},
            "tooltip": {"mode": "single", "yHistogram": True, "showColorScale": True},
            "exemplars": {"color": "rgba(255,0,255,0.7)"},
        },
    )


def table(
    title: str, target: Target, *, w: int = 24, h: int = 7, description: str, hide: list[str]
) -> Panel:
    return Panel(
        "table",
        title,
        [target],
        w,
        h,
        description,
        {"unit": "short", "noValue": "nothing firing", "custom": {"align": "auto"}},
        {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
        transformations=[{"id": "organize", "options": {"excludeByName": {k: True for k in hide}}}],
        idle_ok=True,  # empty = nothing firing
    )


# ---- reusable PromQL ----------------------------------------------------------------------

ERR_PCT = (
    '100 * (sum(rate(http_requests_total{status=~"5.."}[5m])) or vector(0))'
    " / clamp_min(sum(rate(http_requests_total[5m])), 1e-9)"
)
LLM_FAIL_PCT = (
    '100 * (sum(increase(llm_requests_total{status="error"}[15m])) or vector(0))'
    " / clamp_min(sum(increase(llm_requests_total[15m])), 1e-9)"
)
CACHE_HIT = (
    "sum(rate(cache_hits_total[15m]))"
    " / clamp_min(sum(rate(cache_hits_total[15m])) + sum(rate(cache_misses_total[15m])), 1e-9)"
)
VM_MEM_AVAIL = "100 * node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes"
VM_CPU = '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))'
STACK_MEM = f"sum(max by ({BY_SERVICE}) (container_memory_working_set_bytes{P2}))"


def p95_api(window: str = "5m") -> str:
    return (
        "histogram_quantile(0.95, sum by (le) "
        f"(rate(http_request_duration_seconds_bucket[{window}])))"
    )


# ---- dashboards ---------------------------------------------------------------------------


def health() -> Dashboard:
    probes = {
        "App": ('probe_success{instance=~"http://(api|web):.*"}', 4),
        "Data stores": ('probe_success{instance=~"http://qdrant:.*|redis:6379|dynamodb:8000"}', 5),
        "Observability": (
            'probe_success{instance=~"http://(prometheus|grafana|jaeger|cadvisor|redisinsight):.*"}',
            7,
        ),
        "Langfuse": ('probe_success{instance=~"(http://)?langfuse-.*"}', 8),
    }
    endpoints = {
        "App": ('up{job="p2-api"}', 4),
        "Data stores": ('up{job=~"qdrant|redis|postgres|clickhouse|minio"}', 10),
        "Monitoring": ('up{job=~"prometheus|grafana|jaeger|cadvisor|node"}', 10),
    }
    return Dashboard(
        "p2-health",
        "P2 · Service health",
        "Is every component up, is anything alerting, is the app serving users, and is there "
        "room to run? Grafana's home page; every other P2 dashboard is in the dropdown above.",
        [
            Section(
                "0 — At a glance",
                [
                    kpi(
                        "Probes down",
                        Target("count(probe_success == 0) or vector(0)"),
                        description="Health probes failing right now (16 services, every 15 s).",
                        thresholds=[(None, "green"), (1, "red")],
                    ),
                    kpi(
                        "Targets down",
                        Target('count(up{job!~"probe-.*"} == 0) or vector(0)'),
                        description="Metrics endpoints Prometheus cannot scrape right now.",
                        thresholds=[(None, "green"), (1, "red")],
                    ),
                    kpi(
                        "Firing alerts",
                        Target('count(ALERTS{alertstate="firing"}) or vector(0)'),
                        description="Alert rules firing now. Section 2 lists them.",
                        thresholds=[(None, "green"), (1, "red")],
                    ),
                    kpi(
                        "Requests/s",
                        Target("sum(rate(http_requests_total[5m])) or vector(0)"),
                        unit="reqps",
                        decimals=2,
                        description="Every API request, all endpoints (5 min rate).",
                    ),
                    kpi(
                        "p95 (< 2 s)",
                        Target(p95_api("15m")),
                        unit="s",
                        description="95% of requests finished faster than this (15 min window). "
                        "Target: under 2 s.",
                        thresholds=[(None, "green"), (2, "orange"), (4, "red")],
                        no_value="no traffic",
                    ),
                    kpi(
                        "API 5xx %",
                        Target(ERR_PCT),
                        unit="percent",
                        description="Share of requests that failed on the server. Above 1% for "
                        "5 min fires HighErrorRate.",
                        thresholds=[(None, "green"), (1, "red")],
                    ),
                    kpi(
                        "LLM failures",
                        Target(LLM_FAIL_PCT),
                        unit="percent",
                        description="LLM calls that failed (15 min, all providers). The next "
                        "provider answers instead, but costs more.",
                        thresholds=[(None, "green"), (5, "orange"), (50, "red")],
                        no_value="no calls",
                    ),
                    kpi(
                        "VM mem free",
                        Target(VM_MEM_AVAIL),
                        unit="percent",
                        description="Memory still available in the Docker VM (node-exporter). "
                        "Below 15%, starting more (kind, builds) will swap.",
                        thresholds=[(None, "red"), (15, "orange"), (30, "green")],
                    ),
                ],
            ),
            Section(
                "1 — Is every service answering?",
                [
                    Section(
                        "1.1 — Services (health probe every 15 s)",
                        [
                            tiles(
                                name,
                                Target(svc(expr, short=name == "Langfuse"), "{{service}}"),
                                w=w,
                                description=f"{name}: HTTP health endpoints and TCP connects, "
                                "probed from inside the Docker network by blackbox-exporter.",
                            )
                            for name, (expr, w) in probes.items()
                        ],
                    ),
                    Section(
                        "1.2 — Metrics endpoints (scraped every 15 s)",
                        [
                            tiles(
                                name,
                                Target(
                                    svc(expr) if name == "Data stores" else expr,
                                    "{{service}}" if name == "Data stores" else "{{job}}",
                                ),
                                w=w,
                                description=f"{name}: can Prometheus read this component's "
                                "/metrics? DOWN means no data on its dashboards.",
                            )
                            for name, (expr, w) in endpoints.items()
                        ],
                    ),
                    Section(
                        "1.3 — How fast each service answers its probe",
                        [
                            ts(
                                "Probe response time",
                                Target(svc("probe_duration_seconds"), "{{service}}"),
                                unit="s",
                                w=16,
                                description="Time for each health probe to complete. A service "
                                "that slows down here usually fails next.",
                            ),
                            bars(
                                "Slowest right now",
                                Target(svc("probe_duration_seconds"), "{{service}}"),
                                unit="s",
                                w=8,
                                description="Latest probe time per service, slowest first.",
                            ),
                        ],
                        collapsed=True,
                    ),
                ],
            ),
            Section(
                "2 — Is anything firing?",
                [
                    table(
                        "Alerts pending and firing",
                        Target("ALERTS", instant=True, fmt="table"),
                        w=16,
                        h=7,
                        description="Every alert rule that is pending or firing, with its "
                        "labels. Empty is good.",
                        hide=["Time", "__name__", "Value"],
                    ),
                    kpi(
                        "Alert rules loaded",
                        Target("sum(prometheus_rule_group_rules)"),
                        w=4,
                        h=7,
                        description="Rules Prometheus evaluates (shared with Kubernetes).",
                        spark=False,
                    ),
                    kpi(
                        "Rule failures 1h",
                        Target("sum(increase(prometheus_rule_evaluation_failures_total[1h]))"),
                        w=4,
                        h=7,
                        decimals=0,
                        description="Rules that failed to evaluate. Non-zero means an alert "
                        "could stay silent when it should fire.",
                        thresholds=[(None, "green"), (1, "red")],
                        spark=False,
                    ),
                ],
            ),
            Section(
                "3 — Is the app serving users?",
                [
                    ts(
                        "Responses/s by status",
                        Target("sum by (status) (rate(http_requests_total[5m]))", "{{status}}"),
                        unit="reqps",
                        w=8,
                        stack=True,
                        description="All API responses by HTTP status. 401 and 429 are the API "
                        "refusing as designed; 5xx are failures.",
                    ),
                    ts(
                        "API p95 latency vs the 2 s target",
                        Target(p95_api(), "p95"),
                        unit="s",
                        w=8,
                        line=2,
                        description="The dashed line is the NFR. Details per endpoint: "
                        "P2 · API & LLM.",
                    ),
                    ts(
                        "LLM calls/min by provider and outcome",
                        Target(
                            "60 * sum by (provider, status) (rate(llm_requests_total[5m]))",
                            "{{provider}} {{status}}",
                        ),
                        w=8,
                        description="An error on one provider followed by ok on the next is a "
                        "failover (Groq → OpenAI → Anthropic).",
                    ),
                ],
            ),
            Section(
                "4 — Is there room to run?",
                [
                    ts(
                        "Docker VM memory",
                        Target(
                            "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "used"
                        ),
                        Target("node_memory_MemAvailable_bytes", "available"),
                        Target(
                            "node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes", "swap used"
                        ),
                        unit="bytes",
                        w=8,
                        description="The whole VM: P2, kind and any other project's containers. "
                        "Swap in use means memory ran short.",
                    ),
                    ts(
                        "Docker VM CPU %",
                        Target(VM_CPU, "busy"),
                        unit="percent",
                        max_=100,
                        w=8,
                        description="Share of all VM cores busy (node-exporter).",
                    ),
                    bars(
                        "Biggest containers (memory)",
                        Target(
                            f"topk(10, max by ({BY_SERVICE}) (container_memory_working_set_bytes{P2}))",
                            f"{{{{{BY_SERVICE}}}}}",
                        ),
                        unit="bytes",
                        w=8,
                        description="P2's ten largest containers right now. Every container: "
                        "P2 · Docker VM & containers.",
                    ),
                ],
            ),
        ],
    )


def _provider(name: str, provider: str, collapsed: bool = True) -> Section:
    sel = f'provider="{provider}"'
    return Section(
        name,
        [
            ts(
                "Calls/min by outcome",
                Target(
                    f"60 * sum by (status) (rate(llm_requests_total{{{sel}}}[5m]))", "{{status}}"
                ),
                w=6,
                h=7,
                bars=True,
                description="ok = answered; error = failed (the next provider tried).",
                idle="not called in this window",
            ),
            kpi(
                "Failure % (15m)",
                Target(
                    f'100 * (sum(increase(llm_requests_total{{{sel},status="error"}}[15m])) or vector(0))'
                    f" / clamp_min(sum(increase(llm_requests_total{{{sel}}}[15m])), 1e-9)"
                ),
                unit="percent",
                w=4,
                h=7,
                description="Above 50% of 3+ calls for 5 min fires LLMProviderFailing.",
                thresholds=[(None, "green"), (5, "orange"), (50, "red")],
                no_value="not called",
                idle_ok=True,
            ),
            ts(
                "Latency p50 / p95",
                *[
                    Target(
                        f"histogram_quantile({q}, sum by (le) "
                        f"(rate(llm_request_duration_seconds_bucket{{{sel}}}[5m])))",
                        f"p{int(float(q) * 100)}",
                    )
                    for q in ("0.5", "0.95")
                ],
                unit="s",
                w=7,
                h=7,
                description="Time per LLM call, including its hidden reasoning when the model "
                "has any.",
                idle="not called in this window",
            ),
            ts(
                "Tokens/min (input, output)",
                Target(f"60 * sum by (type) (rate(llm_tokens_total{{{sel}}}[5m]))", "{{type}}"),
                w=7,
                h=7,
                stack=True,
                description="What this provider is billed on.",
                idle="not called in this window",
            ),
        ],
        collapsed=collapsed,
    )


def api_llm() -> Dashboard:
    return Dashboard(
        "p2-api-llm",
        "P2 · API & LLM",
        "Request traffic, latency and errors per endpoint; every LLM call per provider "
        "(failover, latency, tokens); cache effectiveness and the live shopping source; the API "
        "process.",
        [
            Section(
                "0 — At a glance",
                [
                    kpi(
                        "Requests/s",
                        Target("sum(rate(http_requests_total[5m])) or vector(0)"),
                        unit="reqps",
                        decimals=2,
                        description="Every API request, all endpoints.",
                    ),
                    kpi(
                        "p50 latency",
                        Target(
                            "histogram_quantile(0.5, sum by (le) "
                            "(rate(http_request_duration_seconds_bucket[15m])))"
                        ),
                        unit="s",
                        description="Half of all requests finish faster than this.",
                        no_value="no traffic",
                    ),
                    kpi(
                        "p95 (< 2 s)",
                        Target(p95_api("15m")),
                        unit="s",
                        description="95% finish faster than this. Target: under 2 s.",
                        thresholds=[(None, "green"), (2, "orange"), (4, "red")],
                        no_value="no traffic",
                    ),
                    kpi(
                        "5xx %",
                        Target(ERR_PCT),
                        unit="percent",
                        description="Server failures as a share of all requests.",
                        thresholds=[(None, "green"), (1, "red")],
                    ),
                    kpi(
                        "LLM calls/min",
                        Target("60 * sum(rate(llm_requests_total[5m])) or vector(0)"),
                        decimals=1,
                        description="Every call to any LLM provider, failures included.",
                    ),
                    kpi(
                        "LLM failures",
                        Target(LLM_FAIL_PCT),
                        unit="percent",
                        description="Failed LLM calls (15 min); each one fell back to the next "
                        "provider.",
                        thresholds=[(None, "green"), (5, "orange"), (50, "red")],
                        no_value="no calls",
                    ),
                    kpi(
                        "Tokens/min",
                        Target("60 * sum(rate(llm_tokens_total[5m])) or vector(0)"),
                        decimals=0,
                        description="Input + output tokens, all providers: what LLM cost follows.",
                    ),
                    kpi(
                        "Cache hits",
                        Target(CACHE_HIT),
                        unit="percentunit",
                        description="Answers served from Redis. Every aggregate miss spends a "
                        "metered SerpApi search.",
                        thresholds=[(None, "orange"), (0.6, "green")],
                        no_value="no traffic",
                    ),
                ],
            ),
            Section(
                "1 — Who is calling, and how is it going?",
                [
                    Section(
                        "1.1 — Requests",
                        [
                            ts(
                                "Requests/s by endpoint",
                                Target("sum by (path) (rate(http_requests_total[5m]))", "{{path}}"),
                                unit="reqps",
                                description="Health and metrics are Kubernetes' and "
                                "Prometheus' own checks; the rest are users.",
                            ),
                            ts(
                                "Responses/s by status",
                                Target(
                                    "sum by (status) (rate(http_requests_total[5m]))", "{{status}}"
                                ),
                                unit="reqps",
                                stack=True,
                                description="401 = no valid token, 429 = rate-limited: the API "
                                "refusing as designed. 5xx = failures.",
                            ),
                        ],
                    ),
                    Section(
                        "1.2 — Latency",
                        [
                            ts(
                                "p95 latency by endpoint",
                                Target(
                                    "histogram_quantile(0.95, sum by (le, path) "
                                    "(rate(http_request_duration_seconds_bucket[5m])))",
                                    "{{path}}",
                                ),
                                unit="s",
                                line=2,
                                description="Dashed: the 2 s NFR. /chat and /aggregate include "
                                "the LLM; /aggregate also includes SerpApi on a cache miss.",
                            ),
                            heatmap(
                                "Latency distribution (all endpoints)",
                                "sum by (le) (increase(http_request_duration_seconds_bucket[1m]))",
                                description="Each column is a minute; darker cells hold more "
                                "requests. Two bands usually mean cache hits vs misses.",
                            ),
                        ],
                    ),
                    Section(
                        "1.3 — Errors and refusals",
                        [
                            ts(
                                "Server errors (5xx) %",
                                Target(ERR_PCT, "5xx %"),
                                unit="percent",
                                w=8,
                                line=1,
                                description="Dashed: 1%, where HighErrorRate fires after 5 min.",
                            ),
                            ts(
                                "Refusals: 401 and 429",
                                Target(
                                    'sum(rate(http_requests_total{status="401"}[5m])) or vector(0)',
                                    "401 no valid token",
                                ),
                                Target(
                                    'sum(rate(http_requests_total{status="429"}[5m])) or vector(0)',
                                    "429 rate-limited",
                                ),
                                unit="reqps",
                                w=8,
                                description="Auth failing closed and per-user limits working.",
                            ),
                            ts(
                                "Guardrail blocks and no-match answers",
                                Target(
                                    "sum by (kind) (increase(guardrail_blocks_total[1h]))",
                                    "blocked: {{kind}}",
                                ),
                                Target("sum(increase(no_match_total[1h]))", "no match"),
                                w=8,
                                description="Prompt-injection attempts blocked, and questions "
                                "the catalog could not answer (1 h).",
                                idle="none in the last hour",
                            ),
                        ],
                        collapsed=True,
                    ),
                ],
            ),
            Section(
                "2 — The LLM chain: Groq → OpenAI → Anthropic",
                [
                    Section(
                        "2.0 — All providers",
                        [
                            ts(
                                "Calls/min by provider and outcome",
                                Target(
                                    "60 * sum by (provider, status) (rate(llm_requests_total[5m]))",
                                    "{{provider}} {{status}}",
                                ),
                                w=8,
                                description="Which provider answered. An error followed by ok "
                                "on the next provider is a failover.",
                            ),
                            bars(
                                "Failure % by provider (15m)",
                                Target(
                                    '100 * (sum by (provider) (increase(llm_requests_total{status="error"}[15m])) or (sum by (provider) (increase(llm_requests_total[15m])) * 0))'
                                    " / clamp_min(sum by (provider) (increase(llm_requests_total[15m])), 1e-9)",
                                    "{{provider}}",
                                ),
                                unit="percent",
                                w=8,
                                max_=100,
                                thresholds=[(None, "green"), (5, "orange"), (50, "red")],
                                description="Share of each provider's calls that failed.",
                            ),
                            ts(
                                "p95 latency by provider",
                                Target(
                                    "histogram_quantile(0.95, sum by (le, provider) "
                                    "(rate(llm_request_duration_seconds_bucket[5m])))",
                                    "{{provider}}",
                                ),
                                unit="s",
                                w=8,
                                description="Slowest 5% of calls per provider.",
                            ),
                            ts(
                                "Tokens/min by provider and direction",
                                Target(
                                    "60 * sum by (provider, type) (rate(llm_tokens_total[5m]))",
                                    "{{provider}} {{type}}",
                                ),
                                w=12,
                                stack=True,
                                description="Input and output tokens: the basis of every bill.",
                            ),
                            bars(
                                "Tokens in the last 24 h",
                                Target(
                                    "sum by (provider, type) (increase(llm_tokens_total[24h]))",
                                    "{{provider}} {{type}}",
                                ),
                                w=12,
                                description="Per provider and direction, largest first.",
                            ),
                        ],
                    ),
                    _provider("2.1 — Groq (tried first)", "groq"),
                    _provider("2.2 — OpenAI (fallback)", "openai"),
                    _provider("2.3 — Anthropic (last resort)", "anthropic"),
                ],
            ),
            Section(
                "3 — Cache and the live shopping source",
                [
                    ts(
                        "Cache hit ratio by layer",
                        Target(
                            "sum by (layer) (rate(cache_hits_total[15m])) / clamp_min(sum by (layer) (rate(cache_hits_total[15m])) + sum by (layer) (rate(cache_misses_total[15m])), 1e-9)",
                            "{{layer}}",
                        ),
                        unit="percentunit",
                        max_=1,
                        w=6,
                        line=0.6,
                        description="Dashed: the 60% target. Every aggregate miss spends a "
                        "SerpApi search.",
                    ),
                    ts(
                        "Cache hits and misses/s",
                        Target("sum by (layer) (rate(cache_hits_total[5m]))", "hit {{layer}}"),
                        Target("sum by (layer) (rate(cache_misses_total[5m]))", "miss {{layer}}"),
                        unit="ops",
                        w=6,
                        description="Per cache layer: response, aggregate, embedding.",
                    ),
                    ts(
                        "SerpApi searches (last hour)",
                        Target(
                            "sum(increase(serpapi_searches_total[1h])) or vector(0)", "searches"
                        ),
                        w=6,
                        description="Metered searches spent in the trailing hour (free plan: "
                        "250/month; the app caps itself per day and month).",
                    ),
                    ts(
                        "Degraded answers: source unavailable",
                        Target(
                            "sum by (reason) (increase(source_unavailable_total[1h]))", "{{reason}}"
                        ),
                        w=6,
                        description="SerpApi down, out of budget or rejecting the key: the UI "
                        "says so instead of showing nothing.",
                        idle="none: SerpApi answered every search",
                    ),
                ],
            ),
            Section(
                "4 — The API process",
                [
                    ts(
                        "CPU (cores)",
                        Target('rate(process_cpu_seconds_total{job="p2-api"}[5m])', "cpu"),
                        w=6,
                        h=7,
                        description="CPU the API process uses (1 = one full core).",
                    ),
                    ts(
                        "Memory (RSS)",
                        Target('process_resident_memory_bytes{job="p2-api"}', "rss"),
                        unit="bytes",
                        w=6,
                        h=7,
                        description="Includes the BM25 model loaded at start.",
                    ),
                    ts(
                        "Open file descriptors",
                        Target('process_open_fds{job="p2-api"}', "open"),
                        Target('process_max_fds{job="p2-api"}', "limit"),
                        w=6,
                        h=7,
                        description="Sockets and files. Climbing without falling is a leak.",
                    ),
                    ts(
                        "Python GC collections/s",
                        Target(
                            'sum by (generation) (rate(python_gc_collections_total{job="p2-api"}[5m]))',
                            "gen {{generation}}",
                        ),
                        w=6,
                        h=7,
                        description="Garbage collection by generation.",
                    ),
                ],
                collapsed=True,
            ),
        ],
        shared=True,
    )


def _redis(number: str, title: str, instance: str, collapsed: bool) -> Section:
    sel = f'instance="{instance}"'
    return Section(
        f"{number} — {title}",
        [
            Section(
                f"{number}.1 — Health",
                [
                    kpi(
                        "Up",
                        Target(f"redis_up{{{sel}}}"),
                        description="Can the exporter talk to this Redis?",
                        thresholds=RED_GREEN,
                        mappings=UP_DOWN,
                        spark=False,
                    ),
                    kpi(
                        "Uptime",
                        Target(f"redis_uptime_in_seconds{{{sel}}}"),
                        unit="dtdurations",
                        description="Since this Redis last started.",
                    ),
                    kpi(
                        "Memory",
                        Target(f"redis_memory_used_bytes{{{sel}}}"),
                        unit="bytes",
                        description="Data plus overhead.",
                    ),
                    kpi(
                        "Keys",
                        Target(f"sum(redis_db_keys{{{sel}}})"),
                        description="All databases.",
                    ),
                    kpi(
                        "Clients",
                        Target(f"redis_connected_clients{{{sel}}}"),
                        description="Open client connections.",
                    ),
                    kpi(
                        "Hit ratio",
                        Target(
                            f"rate(redis_keyspace_hits_total{{{sel}}}[15m]) / clamp_min(rate(redis_keyspace_hits_total{{{sel}}}[15m]) + rate(redis_keyspace_misses_total{{{sel}}}[15m]), 1e-9)"
                        ),
                        unit="percentunit",
                        description="Lookups that found their key (15 min).",
                        no_value="idle",
                    ),
                    kpi(
                        "AOF writes",
                        Target(f"redis_aof_last_write_status{{{sel}}}"),
                        description="Last append-only-file write. Data survives a restart "
                        "only while this is OK.",
                        thresholds=RED_GREEN,
                        mappings=OK_FAILED,
                        spark=False,
                    ),
                    kpi(
                        "Evicted (1h)",
                        Target(f"increase(redis_evicted_keys_total{{{sel}}}[1h])"),
                        decimals=0,
                        description="Keys thrown out because memory was full. Non-zero means "
                        "the cache is too small for its data.",
                        thresholds=[(None, "green"), (1, "orange")],
                    ),
                    ts(
                        "Commands/s",
                        Target(f"rate(redis_commands_processed_total{{{sel}}}[5m])", "commands"),
                        unit="ops",
                        description="Every command Redis executed.",
                    ),
                    ts(
                        "Memory",
                        Target(f"redis_memory_used_bytes{{{sel}}}", "used"),
                        Target(f"redis_memory_used_rss_bytes{{{sel}}}", "rss"),
                        unit="bytes",
                        description="Used by data vs held from the OS.",
                    ),
                ],
            ),
            Section(
                f"{number}.2 — Commands, keys and traffic",
                [
                    ts(
                        "Top commands/s",
                        Target(
                            f"topk(6, sum by (cmd) (rate(redis_commands_total{{{sel}}}[5m])))",
                            "{{cmd}}",
                        ),
                        unit="ops",
                        w=8,
                        description="The six busiest commands.",
                    ),
                    ts(
                        "Average latency by command",
                        Target(
                            f"topk(6, sum by (cmd) (rate(redis_commands_duration_seconds_total{{{sel}}}[5m])) / clamp_min(sum by (cmd) (rate(redis_commands_total{{{sel}}}[5m])), 1e-9))",
                            "{{cmd}}",
                        ),
                        unit="s",
                        w=8,
                        description="Time Redis spends per call, slowest six commands.",
                    ),
                    ts(
                        "Keys expired and evicted/s",
                        Target(f"rate(redis_expired_keys_total{{{sel}}}[5m])", "expired"),
                        Target(f"rate(redis_evicted_keys_total{{{sel}}}[5m])", "evicted"),
                        w=8,
                        description="Expired = TTL reached (normal). Evicted = memory full.",
                    ),
                    ts(
                        "Network in/out",
                        Target(f"rate(redis_net_input_bytes_total{{{sel}}}[5m])", "in"),
                        Target(f"rate(redis_net_output_bytes_total{{{sel}}}[5m])", "out"),
                        unit="Bps",
                        w=12,
                        description="Bytes to and from clients.",
                    ),
                    ts(
                        "Connections received and rejected/s",
                        Target(f"rate(redis_connections_received_total{{{sel}}}[5m])", "received"),
                        Target(f"rate(redis_rejected_connections_total{{{sel}}}[5m])", "rejected"),
                        w=12,
                        description="Rejected connections mean maxclients was reached.",
                    ),
                ],
                collapsed=True,
            ),
        ],
        collapsed=collapsed,
    )


def data_stores() -> Dashboard:
    pg = 'datname="langfuse"'
    return Dashboard(
        "p2-data-stores",
        "P2 · Data stores",
        "Every store, top-down: Qdrant (catalog vectors), Redis (app cache, Langfuse queue), "
        "Langfuse's Postgres, ClickHouse and MinIO, and DynamoDB-local (chat history).",
        [
            Section(
                "0 — At a glance",
                [
                    kpi(
                        "Vectors",
                        Target("sum(collections_vector_total)"),
                        description="Across all collections: the product catalog and the "
                        "semantic answer cache.",
                    ),
                    kpi(
                        "Redis memory",
                        Target('redis_memory_used_bytes{instance="app-redis"}'),
                        unit="bytes",
                        description="The app cache: answers, embeddings, budgets, rate limits.",
                    ),
                    kpi(
                        "Cache hits",
                        Target(CACHE_HIT),
                        unit="percentunit",
                        description="Answers served from the cache (target ≥ 60%).",
                        thresholds=[(None, "orange"), (0.6, "green")],
                        no_value="no traffic",
                    ),
                    kpi(
                        "PG conns",
                        Target(f"pg_stat_database_numbackends{{{pg}}}"),
                        description="Langfuse's open connections to its metadata database.",
                    ),
                    kpi(
                        "PG size",
                        Target(f"pg_database_size_bytes{{{pg}}}"),
                        unit="bytes",
                        description="The langfuse database on disk.",
                    ),
                    kpi(
                        "CH queries/s",
                        Target("rate(ClickHouseProfileEvents_Query[5m])"),
                        unit="ops",
                        decimals=2,
                        description="Langfuse reading and writing traces.",
                    ),
                    kpi(
                        "MinIO used",
                        Target("minio_cluster_usage_total_bytes"),
                        unit="bytes",
                        description="Langfuse's raw events and media.",
                    ),
                    kpi(
                        "DynamoDB",
                        Target('probe_success{instance="dynamodb:8000"}'),
                        description="DynamoDB-local has no metrics endpoint: a TCP probe says "
                        "whether it is up.",
                        thresholds=RED_GREEN,
                        mappings=UP_DOWN,
                        spark=False,
                    ),
                ],
            ),
            Section(
                "1 — Qdrant · catalog vectors",
                [
                    Section(
                        "1.1 — Health",
                        [
                            kpi(
                                "Collections",
                                Target("collections_total"),
                                w=4,
                                description="Collections stored.",
                            ),
                            kpi(
                                "Vectors",
                                Target("sum(collections_vector_total)"),
                                w=4,
                                description="Indexed vectors.",
                            ),
                            kpi(
                                "Memory",
                                Target("memory_resident_bytes"),
                                unit="bytes",
                                w=4,
                                description="Qdrant's resident memory.",
                            ),
                            kpi(
                                "Failed (1h)",
                                Target("sum(increase(rest_responses_fail_total[1h]))"),
                                w=4,
                                decimals=0,
                                description="Requests Qdrant answered with an error.",
                                thresholds=[(None, "green"), (1, "orange")],
                            ),
                            kpi(
                                "Search p95",
                                Target(
                                    "histogram_quantile(0.95, sum by (le) "
                                    "(rate(rest_responses_duration_seconds_bucket[15m])))"
                                ),
                                unit="s",
                                w=4,
                                description="Slowest 5% of Qdrant calls (15 min).",
                                no_value="no searches",
                                idle_ok=True,
                            ),
                            kpi(
                                "Calls/s",
                                Target("sum(rate(rest_responses_total[5m]))"),
                                unit="reqps",
                                decimals=2,
                                w=4,
                                description="Searches, upserts and health checks.",
                            ),
                        ],
                    ),
                    Section(
                        "1.2 — Calls and latency by endpoint",
                        [
                            ts(
                                "REST calls/s by endpoint",
                                Target(
                                    "sum by (endpoint, method) (rate(rest_responses_total[5m]))",
                                    "{{method}} {{endpoint}}",
                                ),
                                unit="reqps",
                                description="Each search the API makes shows up here.",
                            ),
                            ts(
                                "p95 latency by endpoint",
                                Target(
                                    "histogram_quantile(0.95, sum by (le, endpoint) "
                                    "(rate(rest_responses_duration_seconds_bucket[5m])))",
                                    "{{endpoint}}",
                                ),
                                unit="s",
                                description="Slowest 5% per endpoint.",
                                idle="no searches in this window",
                            ),
                        ],
                        collapsed=True,
                    ),
                ],
            ),
            _redis("2", "Redis · app cache", "app-redis", collapsed=False),
            _redis("3", "Redis · Langfuse queue", "langfuse-redis", collapsed=True),
            Section(
                "4 — Postgres · Langfuse metadata",
                [
                    kpi(
                        "Up",
                        Target("pg_up"),
                        description="Can the exporter log in?",
                        thresholds=RED_GREEN,
                        mappings=UP_DOWN,
                        spark=False,
                    ),
                    kpi(
                        "Connections",
                        Target(f"pg_stat_database_numbackends{{{pg}}}"),
                        description="Open connections to the langfuse database.",
                    ),
                    kpi(
                        "Max conns",
                        Target("pg_settings_max_connections"),
                        description="The server's limit.",
                    ),
                    kpi(
                        "Cache hit ratio",
                        Target(
                            f"rate(pg_stat_database_blks_hit{{{pg}}}[15m]) / clamp_min(rate(pg_stat_database_blks_hit{{{pg}}}[15m]) + rate(pg_stat_database_blks_read{{{pg}}}[15m]), 1e-9)"
                        ),
                        unit="percentunit",
                        description="Reads served from memory instead of disk. Healthy: above 99%.",
                        thresholds=[(None, "orange"), (0.99, "green")],
                        no_value="idle",
                    ),
                    kpi(
                        "Deadlocks 24h",
                        Target(f"increase(pg_stat_database_deadlocks{{{pg}}}[24h])"),
                        decimals=0,
                        description="Transactions killed by a deadlock.",
                        thresholds=[(None, "green"), (1, "red")],
                    ),
                    kpi(
                        "Database size",
                        Target(f"pg_database_size_bytes{{{pg}}}"),
                        unit="bytes",
                        description="On disk.",
                    ),
                    kpi(
                        "Rollbacks/s",
                        Target(f"rate(pg_stat_database_xact_rollback{{{pg}}}[5m])"),
                        unit="ops",
                        decimals=2,
                        description="Aborted transactions.",
                    ),
                    kpi(
                        "Locks",
                        Target("sum(pg_locks_count)"),
                        description="All lock modes, all databases.",
                    ),
                    ts(
                        "Transactions/s",
                        Target(f"rate(pg_stat_database_xact_commit{{{pg}}}[5m])", "commit"),
                        Target(f"rate(pg_stat_database_xact_rollback{{{pg}}}[5m])", "rollback"),
                        unit="ops",
                        w=8,
                        description="Langfuse's writes and reads.",
                    ),
                    ts(
                        "Rows/s",
                        *[
                            Target(f"rate(pg_stat_database_tup_{op}{{{pg}}}[5m])", op)
                            for op in ("fetched", "inserted", "updated", "deleted")
                        ],
                        unit="rowsps",
                        w=8,
                        description="Row activity by kind.",
                    ),
                    ts(
                        "Locks by mode",
                        Target("sum by (mode) (pg_locks_count)", "{{mode}}"),
                        w=8,
                        description="Exclusive locks piling up mean contention.",
                    ),
                ],
                collapsed=True,
            ),
            Section(
                "5 — ClickHouse · Langfuse traces",
                [
                    kpi(
                        "Uptime",
                        Target("ClickHouseAsyncMetrics_Uptime"),
                        unit="dtdurations",
                        description="Since ClickHouse last started.",
                    ),
                    kpi(
                        "Running",
                        Target("ClickHouseMetrics_Query"),
                        description="Executing right now.",
                    ),
                    kpi(
                        "Memory tracked",
                        Target("ClickHouseMetrics_MemoryTracking"),
                        unit="bytes",
                        description="Memory ClickHouse accounts for.",
                    ),
                    kpi(
                        "Parts",
                        Target("ClickHouseAsyncMetrics_TotalPartsOfMergeTreeTables"),
                        description="Data parts awaiting merges. Thousands means inserts are too "
                        "small or merges are behind.",
                        thresholds=[(None, "green"), (1000, "orange"), (3000, "red")],
                    ),
                    kpi(
                        "Failed (1h)",
                        Target("increase(ClickHouseProfileEvents_FailedQuery[1h])"),
                        decimals=0,
                        description="Queries that errored.",
                        thresholds=[(None, "green"), (1, "orange")],
                    ),
                    kpi(
                        "Rows in/s",
                        Target("rate(ClickHouseProfileEvents_InsertedRows[5m])"),
                        unit="rowsps",
                        decimals=1,
                        description="Trace rows written.",
                    ),
                    kpi(
                        "Merges",
                        Target("ClickHouseMetrics_Merge"),
                        description="Background merges in progress.",
                    ),
                    kpi(
                        "Connections",
                        Target(
                            "ClickHouseMetrics_TCPConnection + ClickHouseMetrics_HTTPConnection"
                        ),
                        description="TCP + HTTP clients.",
                    ),
                    ts(
                        "Queries/s by kind",
                        Target("rate(ClickHouseProfileEvents_SelectQuery[5m])", "select"),
                        Target("rate(ClickHouseProfileEvents_InsertQuery[5m])", "insert"),
                        Target("rate(ClickHouseProfileEvents_FailedQuery[5m])", "failed"),
                        unit="ops",
                        w=8,
                        description="The Langfuse UI reads; the worker inserts.",
                    ),
                    ts(
                        "Inserted rows and bytes/s",
                        Target("rate(ClickHouseProfileEvents_InsertedRows[5m])", "rows"),
                        Target("rate(ClickHouseProfileEvents_InsertedBytes[5m])", "bytes"),
                        w=8,
                        description="Write volume.",
                    ),
                    ts(
                        "Memory tracked",
                        Target("ClickHouseMetrics_MemoryTracking", "memory"),
                        unit="bytes",
                        w=8,
                        description="Spikes come from large queries.",
                    ),
                ],
                collapsed=True,
            ),
            Section(
                "6 — MinIO · Langfuse blobs",
                [
                    kpi(
                        "Health",
                        Target("minio_cluster_health_status"),
                        description="MinIO's own cluster health check.",
                        thresholds=RED_GREEN,
                        mappings=OK_FAILED,
                        spark=False,
                    ),
                    kpi(
                        "Used",
                        Target("minio_cluster_usage_total_bytes"),
                        unit="bytes",
                        description="All buckets.",
                    ),
                    kpi(
                        "Objects",
                        Target("minio_cluster_usage_object_total"),
                        description="One per ingested event or media file.",
                    ),
                    kpi(
                        "Buckets",
                        Target("minio_cluster_bucket_total"),
                        description="Langfuse uses one.",
                    ),
                    kpi(
                        "Free",
                        Target("minio_cluster_capacity_usable_free_bytes"),
                        unit="bytes",
                        description="Disk space MinIO can still use.",
                    ),
                    kpi(
                        "S3 errors 1h",
                        Target("sum(increase(minio_s3_requests_errors_total[1h]))"),
                        decimals=0,
                        description="Failed S3 calls.",
                        thresholds=[(None, "green"), (1, "orange")],
                    ),
                    kpi(
                        "Memory",
                        Target("minio_node_process_resident_memory_bytes"),
                        unit="bytes",
                        description="MinIO's resident memory.",
                    ),
                    kpi(
                        "In flight",
                        Target("sum(minio_s3_requests_inflight_total)"),
                        description="S3 calls being served now.",
                    ),
                    ts(
                        "S3 requests/s by API",
                        Target("sum by (api) (rate(minio_s3_requests_total[5m]))", "{{api}}"),
                        unit="reqps",
                        w=12,
                        description="PutObject = Langfuse storing an event.",
                    ),
                    ts(
                        "Traffic in/out",
                        Target("rate(minio_s3_traffic_received_bytes[5m])", "received"),
                        Target("rate(minio_s3_traffic_sent_bytes[5m])", "sent"),
                        unit="Bps",
                        w=12,
                        description="Bytes stored and served.",
                    ),
                ],
                collapsed=True,
            ),
            Section(
                "7 — DynamoDB-local · chat history",
                [
                    tiles(
                        "DynamoDB-local",
                        Target('probe_success{instance="dynamodb:8000"}', "dynamodb"),
                        w=4,
                        h=5,
                        description="No metrics endpoint: a TCP connect probe every 15 s.",
                    ),
                    ts(
                        "Connect time",
                        Target('probe_duration_seconds{instance="dynamodb:8000"}', "connect"),
                        unit="s",
                        w=20,
                        h=5,
                        description="How long a TCP connect takes. In-memory store: a restart "
                        "empties it, by design.",
                    ),
                ],
                collapsed=True,
            ),
        ],
    )


def containers() -> Dashboard:
    legend = f"{{{{{BY_SERVICE}}}}}"
    return Dashboard(
        "p2-containers",
        "P2 · Docker VM & containers",
        "The Docker VM itself (node-exporter), every P2 container (cAdvisor), and the "
        "monitoring stack watching them.",
        [
            Section(
                "0 — At a glance",
                [
                    kpi(
                        "VM mem free",
                        Target(VM_MEM_AVAIL),
                        unit="percent",
                        description="Available memory in the Docker VM, whoever uses it.",
                        thresholds=[(None, "red"), (15, "orange"), (30, "green")],
                    ),
                    kpi(
                        "VM CPU",
                        Target(VM_CPU),
                        unit="percent",
                        description="All cores, 5 min average.",
                        thresholds=[(None, "green"), (70, "orange"), (90, "red")],
                    ),
                    kpi(
                        "Swap used",
                        Target("node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes"),
                        unit="bytes",
                        description="Memory pushed to disk. Growing means the VM ran short.",
                        thresholds=[(None, "green"), (1e9, "orange"), (3e9, "red")],
                    ),
                    kpi(
                        "Disk free",
                        Target(
                            '100 * max(node_filesystem_avail_bytes / node_filesystem_size_bytes and on (device, mountpoint) topk(1, node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs"}))'
                        ),
                        unit="percent",
                        description="Docker's disk (images, volumes, build cache): the "
                        "largest real filesystem in the VM.",
                        thresholds=[(None, "red"), (10, "orange"), (25, "green")],
                    ),
                    kpi(
                        "Containers",
                        Target(
                            f"count(count by ({BY_SERVICE}) (container_memory_working_set_bytes{P2}))"
                        ),
                        description="P2 compose containers cAdvisor sees running.",
                    ),
                    kpi(
                        "P2 memory",
                        Target(STACK_MEM),
                        unit="bytes",
                        description="Working set of the whole compose stack.",
                    ),
                    kpi(
                        "P2 CPU",
                        Target(
                            f"sum(max by ({BY_SERVICE}) (rate(container_cpu_usage_seconds_total{P2}[5m])))"
                        ),
                        decimals=2,
                        description="1 = one full core.",
                    ),
                    kpi(
                        "(Re)starts 1h",
                        Target(
                            f"sum(changes(max by ({BY_SERVICE}) (container_start_time_seconds{P2})[1h:1m])) or vector(0)"
                        ),
                        decimals=0,
                        description="P2 containers created or restarted in the last hour. "
                        "make up/upv recreate them; a count you didn't cause is a crash.",
                        thresholds=[(None, "green"), (1, "orange")],
                    ),
                ],
            ),
            Section(
                "1 — The Docker VM",
                [
                    Section(
                        "1.1 — CPU and memory",
                        [
                            ts(
                                "CPU by mode",
                                Target(
                                    '100 * sum by (mode) (rate(node_cpu_seconds_total{mode!="idle"}[5m])) / scalar(count(node_cpu_seconds_total{mode="idle"}))',
                                    "{{mode}}",
                                ),
                                unit="percent",
                                w=8,
                                stack=True,
                                description="Busy share of all cores. iowait = waiting on disk.",
                            ),
                            ts(
                                "Memory",
                                Target(
                                    "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
                                    "used",
                                ),
                                Target(
                                    "node_memory_Cached_bytes + node_memory_Buffers_bytes",
                                    "cache",
                                ),
                                Target("node_memory_MemAvailable_bytes", "available"),
                                Target(
                                    "node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes",
                                    "swap used",
                                ),
                                unit="bytes",
                                w=8,
                                description="Cache is given back on demand; swap in use means "
                                "it wasn't enough.",
                            ),
                            ts(
                                "Load average",
                                Target("node_load1", "1 min"),
                                Target("node_load5", "5 min"),
                                Target("node_load15", "15 min"),
                                w=8,
                                description="Runnable tasks. Above the core count, work queues.",
                            ),
                        ],
                    ),
                    Section(
                        "1.2 — Pressure, disk and network",
                        [
                            ts(
                                "Pressure: time stalled waiting",
                                Target(
                                    "rate(node_pressure_memory_waiting_seconds_total[5m])",
                                    "memory",
                                ),
                                Target("rate(node_pressure_io_waiting_seconds_total[5m])", "io"),
                                Target("rate(node_pressure_cpu_waiting_seconds_total[5m])", "cpu"),
                                unit="percentunit",
                                w=8,
                                description="Share of time tasks waited on a resource (Linux "
                                "PSI): the clearest sign of an overfull VM.",
                            ),
                            ts(
                                "Disk I/O",
                                Target("sum(rate(node_disk_read_bytes_total[5m]))", "read"),
                                Target("sum(rate(node_disk_written_bytes_total[5m]))", "write"),
                                unit="Bps",
                                w=8,
                                description="All disks of the VM.",
                            ),
                            ts(
                                "Network",
                                Target(
                                    'sum(rate(node_network_receive_bytes_total{device!="lo"}[5m]))',
                                    "received",
                                ),
                                Target(
                                    'sum(rate(node_network_transmit_bytes_total{device!="lo"}[5m]))',
                                    "sent",
                                ),
                                unit="Bps",
                                w=8,
                                description="node-exporter's view of the network.",
                            ),
                        ],
                        collapsed=True,
                    ),
                ],
            ),
            Section(
                "2 — Every P2 container",
                [
                    Section(
                        "2.1 — Memory and CPU",
                        [
                            ts(
                                "Memory by service",
                                Target(
                                    f"max by ({BY_SERVICE}) (container_memory_working_set_bytes{P2})",
                                    legend,
                                ),
                                unit="bytes",
                                w=16,
                                h=10,
                                stack=True,
                                legend="right",
                                description="Working set per container, stacked: the total is "
                                "P2's footprint.",
                            ),
                            bars(
                                "Largest now",
                                Target(
                                    f"topk(10, max by ({BY_SERVICE}) (container_memory_working_set_bytes{P2}))",
                                    legend,
                                ),
                                unit="bytes",
                                w=8,
                                h=10,
                                description="The ten largest, biggest first.",
                            ),
                            ts(
                                "CPU by service (cores)",
                                Target(
                                    f"max by ({BY_SERVICE}) (rate(container_cpu_usage_seconds_total{P2}[5m]))",
                                    legend,
                                ),
                                w=16,
                                h=9,
                                legend="right",
                                description="1 = one full core.",
                            ),
                            bars(
                                "Busiest now (cores)",
                                Target(
                                    f"topk(10, max by ({BY_SERVICE}) (rate(container_cpu_usage_seconds_total{P2}[5m])))",
                                    legend,
                                ),
                                w=8,
                                h=9,
                                description="The ten busiest, busiest first.",
                            ),
                        ],
                    ),
                    Section(
                        "2.2 — Network and disk",
                        [
                            ts(
                                "Network received",
                                Target(
                                    f"max by ({BY_SERVICE}) (rate(container_network_receive_bytes_total{P2}[5m]))",
                                    legend,
                                ),
                                unit="Bps",
                                w=8,
                                description="Per container.",
                            ),
                            ts(
                                "Network sent",
                                Target(
                                    f"max by ({BY_SERVICE}) (rate(container_network_transmit_bytes_total{P2}[5m]))",
                                    legend,
                                ),
                                unit="Bps",
                                w=8,
                                description="Per container.",
                            ),
                            ts(
                                "Disk writes",
                                Target(
                                    f"topk(8, max by ({BY_SERVICE}) (rate(container_fs_writes_bytes_total{P2}[5m])))",
                                    legend,
                                ),
                                unit="Bps",
                                w=8,
                                description="The eight heaviest writers.",
                            ),
                        ],
                        collapsed=True,
                    ),
                    Section(
                        "2.3 — Restarts, OOM kills and memory pressure",
                        [
                            ts(
                                "Memory pressure by service",
                                Target(
                                    f"topk(6, max by ({BY_SERVICE}) (rate(container_pressure_memory_waiting_seconds_total{P2}[5m])))",
                                    legend,
                                ),
                                unit="percentunit",
                                w=8,
                                description="Share of time each container waited for memory.",
                            ),
                            ts(
                                "Restarts (1h)",
                                Target(
                                    f"changes(max by ({BY_SERVICE}) (container_start_time_seconds{P2})[1h:1m])",
                                    legend,
                                ),
                                w=8,
                                bars=True,
                                description="Containers that started again within the hour.",
                            ),
                            ts(
                                "OOM kills (1h)",
                                Target(
                                    f"max by ({BY_SERVICE}) (increase(container_oom_events_total{P2}[1h])) > 0",
                                    legend,
                                ),
                                w=8,
                                bars=True,
                                description="Killed for exceeding memory. Empty is good.",
                                idle="none: good",
                            ),
                        ],
                        collapsed=True,
                    ),
                ],
            ),
            Section(
                "3 — The monitoring stack itself",
                [
                    kpi(
                        "Series stored",
                        Target("prometheus_tsdb_head_series"),
                        w=4,
                        description="Distinct time series Prometheus holds.",
                    ),
                    kpi(
                        "Samples/s ingested",
                        Target("rate(prometheus_tsdb_head_samples_appended_total[5m])"),
                        w=4,
                        decimals=0,
                        description="Data points written per second.",
                    ),
                    kpi(
                        "Prometheus memory",
                        Target('process_resident_memory_bytes{job="prometheus"}'),
                        unit="bytes",
                        w=4,
                        description="Resident memory.",
                    ),
                    kpi(
                        "Jaeger spans/s",
                        Target("sum(rate(jaeger_collector_spans_received_total[5m]))"),
                        w=4,
                        decimals=2,
                        description="Trace spans arriving from the API.",
                    ),
                    kpi(
                        "Spans dropped (1h)",
                        Target("sum(increase(jaeger_collector_spans_dropped_total[1h]))"),
                        w=4,
                        decimals=0,
                        description="Spans Jaeger could not store.",
                        thresholds=[(None, "green"), (1, "orange")],
                    ),
                    kpi(
                        "Grafana requests/s",
                        Target("sum(rate(grafana_http_request_duration_seconds_count[5m]))"),
                        w=4,
                        decimals=2,
                        description="Dashboards being viewed.",
                    ),
                    ts(
                        "Scrape duration by job",
                        Target("max by (job) (scrape_duration_seconds)", "{{job}}"),
                        unit="s",
                        w=12,
                        description="A target taking near its 10 s timeout is about to drop.",
                    ),
                    ts(
                        "Samples per scrape by job",
                        Target("sum by (job) (scrape_samples_scraped)", "{{job}}"),
                        w=12,
                        description="Metric volume each target exports.",
                    ),
                ],
                collapsed=True,
            ),
        ],
    )


DASHBOARDS = (health, api_llm, data_stores, containers)

LINKS: list[dict[str, Any]] = [
    {"title": "P2 dashboards", "type": "dashboards", "tags": ["p2"], "asDropdown": True},
    {"title": "Web app", "type": "link", "url": "http://localhost:2012"},
    {"title": "Langfuse", "type": "link", "url": "http://localhost:2008"},
    {"title": "Jaeger", "type": "link", "url": "http://localhost:2006"},
    {"title": "Prometheus", "type": "link", "url": "http://localhost:2009/targets"},
    {"title": "RedisInsight", "type": "link", "url": "http://localhost:2005"},
]


# ---- layout -------------------------------------------------------------------------------


def place(panels: list[Panel]) -> list[tuple[Panel, int, int]]:
    """Left to right, wrapping at 24 columns: (panel, x, y)."""
    out, x, y, line_h = [], 0, 0, 0
    for p in panels:
        if x + p.w > 24:
            x, y, line_h = 0, y + line_h, 0
        out.append((p, x, y))
        x += p.w
        line_h = max(line_h, p.h)
    return out


def panels_of(section: Section) -> list[Panel]:
    kinds = {isinstance(c, Section) for c in section.children}
    if len(kinds) > 1:
        raise ValueError(f"{section.title}: mix of panels and sub-sections")
    return [c for c in section.children if isinstance(c, Panel)]


def walk(sections: list[Section]) -> list[Panel]:
    out: list[Panel] = []
    for s in sections:
        out += panels_of(s)
        out += walk([c for c in s.children if isinstance(c, Section)])
    return out


# ---- v2 (Grafana 13, compose) -------------------------------------------------------------


def v2_query(t: Target, ref: str) -> dict[str, Any]:
    spec: dict[str, Any] = {"expr": t.expr, "legendFormat": t.legend or "__auto"}
    if t.instant:
        spec.update({"instant": True, "range": False})
    if t.fmt != "time_series":
        spec["format"] = t.fmt
    return {
        "kind": "PanelQuery",
        "spec": {
            "query": {
                "kind": "DataQuery",
                "group": "prometheus",
                "version": "v0",
                "datasource": {"name": DS_UID},
                "spec": spec,
            },
            "refId": ref,
            "hidden": False,
        },
    }


def v2_element(p: Panel, pid: int) -> dict[str, Any]:
    return {
        "kind": "Panel",
        "spec": {
            "id": pid,
            "title": p.title,
            "description": p.description,
            "links": p.links,
            "data": {
                "kind": "QueryGroup",
                "spec": {
                    "queries": [v2_query(t, chr(65 + i)) for i, t in enumerate(p.targets)],
                    "transformations": [
                        {"kind": t["id"], "spec": {"id": t["id"], "options": t["options"]}}
                        for t in p.transformations
                    ],
                    "queryOptions": {},
                },
            },
            "vizConfig": {
                "kind": "VizConfig",
                "group": p.kind,
                "version": "",
                "spec": {
                    "options": p.options,
                    "fieldConfig": {"defaults": p.defaults, "overrides": p.overrides},
                },
            },
        },
    }


def v2_layout(sections: list[Section], ids: dict[int, str]) -> dict[str, Any]:
    rows = []
    for s in sections:
        subs = [c for c in s.children if isinstance(c, Section)]
        if subs:
            inner = v2_layout(subs, ids)
        else:
            inner = {
                "kind": "GridLayout",
                "spec": {
                    "items": [
                        {
                            "kind": "GridLayoutItem",
                            "spec": {
                                "x": x,
                                "y": y,
                                "width": p.w,
                                "height": p.h,
                                "element": {"kind": "ElementReference", "name": ids[id(p)]},
                            },
                        }
                        for p, x, y in place(panels_of(s))
                    ]
                },
            }
        rows.append(
            {
                "kind": "RowsLayoutRow",
                "spec": {"title": s.title, "collapse": s.collapsed, "layout": inner},
            }
        )
    return {"kind": "RowsLayout", "spec": {"rows": rows}}


def v2_link(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": link["title"],
        "type": link["type"],
        "icon": "external link" if link["type"] == "link" else "dashboard",
        "tooltip": "",
        "url": link.get("url", ""),
        "tags": link.get("tags", []),
        "asDropdown": link.get("asDropdown", False),
        "targetBlank": link["type"] == "link",
        "includeVars": False,
        "keepTime": link["type"] == "dashboards",
    }


def to_v2(d: Dashboard) -> dict[str, Any]:
    panels = walk(d.sections)
    ids = {id(p): f"panel-{i}" for i, p in enumerate(panels, start=1)}
    return {
        "apiVersion": "dashboard.grafana.app/v2",
        "kind": "Dashboard",
        "metadata": {"name": d.uid},
        "spec": {
            "annotations": [
                {
                    "kind": "AnnotationQuery",
                    "spec": {
                        "query": {
                            "kind": "DataQuery",
                            "group": "grafana",
                            "version": "v0",
                            "datasource": {"name": "-- Grafana --"},
                            "spec": {},
                        },
                        "enable": True,
                        "hide": True,
                        "iconColor": "rgba(0, 211, 255, 1)",
                        "name": "Annotations & Alerts",
                        "builtIn": True,
                        "legacyOptions": {"type": "dashboard"},
                    },
                }
            ],
            "cursorSync": "Crosshair",
            "description": d.description,
            "editable": False,
            "elements": {ids[id(p)]: v2_element(p, i) for i, p in enumerate(panels, start=1)},
            "layout": v2_layout(d.sections, ids),
            "links": [v2_link(link) for link in LINKS],
            "liveNow": False,
            "preload": False,
            "tags": ["p2"],
            "timeSettings": {
                "timezone": "browser",
                "from": "now-1h",
                "to": "now",
                "autoRefresh": "30s",
                "autoRefreshIntervals": ["10s", "30s", "1m", "5m", "15m", "1h"],
                "hideTimepicker": False,
                "fiscalYearStartMonth": 0,
            },
            "title": d.title,
            "variables": [],
        },
    }


# ---- v1 (Grafana 12 on Kubernetes) --------------------------------------------------------


def to_v1(d: Dashboard) -> dict[str, Any]:
    """Classic format: every section that holds panels becomes one plain row."""
    out: list[dict[str, Any]] = []
    y, pid = 0, 0
    ds = {"type": "prometheus", "uid": DS_UID}

    def emit(sections: list[Section]) -> None:
        nonlocal y, pid
        for s in sections:
            panels = panels_of(s)
            if panels:
                pid += 1
                out.append(
                    {
                        "type": "row",
                        "title": s.title,
                        "id": pid,
                        "collapsed": False,
                        "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
                        "panels": [],
                    }
                )
                y += 1
                bottom = y
                for p, x, py in place(panels):
                    pid += 1
                    out.append(
                        {
                            "type": p.kind,
                            "title": p.title,
                            "id": pid,
                            "description": p.description,
                            "datasource": ds,
                            "gridPos": {"x": x, "y": y + py, "w": p.w, "h": p.h},
                            "targets": [
                                {
                                    "refId": chr(65 + i),
                                    "datasource": ds,
                                    "expr": t.expr,
                                    "legendFormat": t.legend,
                                    "instant": t.instant,
                                    "range": not t.instant,
                                    "format": t.fmt,
                                }
                                for i, t in enumerate(p.targets)
                            ],
                            "fieldConfig": {"defaults": p.defaults, "overrides": p.overrides},
                            "options": p.options,
                            "transformations": p.transformations,
                        }
                    )
                    bottom = max(bottom, y + py + p.h)
                y = bottom
            emit([c for c in s.children if isinstance(c, Section)])

    emit(d.sections)
    return {
        "uid": d.uid,
        "title": d.title,
        "description": d.description,
        "tags": ["p2"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "editable": False,
        "graphTooltip": 1,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        # Kubernetes has no localhost UIs: only the dashboards dropdown.
        "links": [
            {
                "title": "P2 dashboards",
                "type": "dashboards",
                "tags": ["p2"],
                "asDropdown": True,
                "includeVars": False,
                "keepTime": True,
            }
        ],
        "panels": out,
        "templating": {"list": []},
        "annotations": {"list": []},
    }


def idle_expressions() -> set[str]:
    """Queries that may return nothing while P2 is idle (`make verify` skips them)."""
    return {
        t.expr for make in DASHBOARDS for p in walk(make().sections) if p.idle_ok for t in p.targets
    }


def expressions(payload: dict[str, Any]) -> list[str]:
    """Every PromQL expression in a v1 or v2 dashboard (used by tests and `make verify`)."""
    if payload.get("apiVersion", "").startswith("dashboard.grafana.app/"):
        return [
            q["spec"]["query"]["spec"]["expr"]
            for el in payload["spec"]["elements"].values()
            for q in el["spec"]["data"]["spec"]["queries"]
        ]
    return [t["expr"] for p in payload["panels"] for t in p.get("targets", []) if t.get("expr")]


def build() -> list[tuple[Path, dict[str, Any]]]:
    out = []
    for make in DASHBOARDS:
        d = make()
        out.append((COMPOSE / f"{d.uid}.json", to_v2(d)))
        if d.shared:
            out.append((SHARED / f"{d.uid}.json", to_v1(d)))
    return out


def main() -> int:
    COMPOSE.mkdir(parents=True, exist_ok=True)
    for path, payload in build():
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {path.relative_to(ROOT)} ({len(expressions(payload))} queries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
