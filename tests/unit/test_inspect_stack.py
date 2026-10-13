"""scripts/inspect_stack.py: the pure logic behind the inspection (no services, no network).

The parity tests run the app's own cache code (aggregate, cached_recommend, the budget guard)
against fakeredis and check the script computes exactly the keys the app writes, so the
document's "clear one query's key" commands can't drift from the code.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import fakeredis
import httpx
import jwt
import pytest
from langchain_core.runnables import RunnableLambda
from scripts import inspect_stack as ins

from core.cache import RedisCache, clear_version_memo
from core.config import get_settings
from core.models import ExplanationSet, Offer, RankingResult, RetrievedProduct
from ops.observability.grafana.build_dashboards import DASHBOARDS, walk
from ops.stack.catalog import load_env
from ops.stack.verify import Verifier
from recommender.aggregator import _budget_keys, aggregate
from recommender.cached import cached_recommend

# ---- secrets never reach the output ------------------------------------------------------------


def test_redactor_blanks_env_secrets_jwts_and_provider_keys() -> None:
    env = {
        "OPENAI_API_KEY": "sk-proj-abcdefghijklmnopqrstuvwxyz0123",
        "AUTH_DEV_SECRET": "dev-secret-change-me-in-prod-0123456789abcdef",
        "LANGFUSE_POSTGRES_PASSWORD": "langfuse-local-dev",
        "WEB_PORT": "2012",
        "GRAFANA_ADMIN_PASSWORD": "admin",  # too short to blank safely: it would hit every "admin"
    }
    redact = ins.Redactor(env)
    token = jwt.encode({"sub": "u"}, "k" * 40, algorithm="HS256")
    text = (
        f"key={env['OPENAI_API_KEY']} secret={env['AUTH_DEV_SECRET']} "
        f"pg={env['LANGFUSE_POSTGRES_PASSWORD']} bearer {token} other gsk_ABCDEFGHIJKLMNOPQRSTUV "
        "port 2012 user admin"
    )
    out = redact(text)
    for secret in (env["OPENAI_API_KEY"], env["AUTH_DEV_SECRET"], "langfuse-local-dev", token):
        assert secret not in out
    assert "gsk_ABCDEFGHIJKLMNOPQRSTUV" not in out
    assert "port 2012" in out and "user admin" in out


# ---- cache keys: parity with the app ------------------------------------------------------------


class _FakeModel:
    def with_structured_output(self, schema: object) -> Any:
        return RunnableLambda(lambda _inputs: ExplanationSet(summary="s", explanations=[]))


def _offer(product_id: str) -> Offer:
    return Offer(
        product_id=product_id,
        title=product_id,
        price=10.0,
        store="Shop",
        product_url=f"https://buy/{product_id}",
        rating=4.0,
        review_count=100,
        position=1,
    )


@pytest.fixture
def client() -> fakeredis.FakeRedis:
    clear_version_memo()  # the L0 memo is process-wide; start each test at a known version
    return fakeredis.FakeRedis(decode_responses=True)


def test_agg_key_matches_what_aggregate_writes(client: fakeredis.FakeRedis) -> None:
    query = "Wireless  Earbuds"
    aggregate(
        query,
        RedisCache(client),
        _FakeModel(),
        k=ins.DISCOVER_K,
        search_fn=lambda q, n: [_offer("A"), _offer("B")],
    )
    written = [str(k) for k in client.scan_iter("agg:*")]
    expected = ins.cache_keys(query, "1", "unused", ks=(ins.DISCOVER_K,))["agg k=6"]
    assert written == [expected]


class _Store:
    def index(self, products: list[Any]) -> None:
        return None

    def max_dense_similarity(self, query_vector: list[float]) -> float:
        return 0.9

    def search(self, query: str, k: int = 5) -> list[RetrievedProduct]:
        return [
            RetrievedProduct(
                product_id="A",
                title="A",
                avg_rating=4.5,
                review_count=50,
                semantic_score=0.9,
                text="bass",
            )
        ]


class _NoSemantic:
    def lookup(
        self, query_vector: list[float], version: str, threshold: float = 0.97
    ) -> RankingResult | None:
        return None

    def store(
        self, query_vector: list[float], version: str, query: str, result: RankingResult
    ) -> None:
        return None


class _Embeddings:
    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 8


def test_resp_and_emb_keys_match_what_cached_recommend_writes(
    client: fakeredis.FakeRedis,
) -> None:
    query = "Good  BASS headphones"
    cached_recommend(query, _Store(), RedisCache(client), _NoSemantic(), _Embeddings(), k=5)
    model = get_settings().embedding_model
    keys = ins.cache_keys(query, "1", model, ks=(5,))
    assert sorted(str(k) for k in client.scan_iter("resp:*")) == [keys["resp k=5"]]
    assert sorted(str(k) for k in client.scan_iter("emb:*")) == [keys["emb"]]


def test_spend_keys_match_the_budget_guard() -> None:
    moment = dt.datetime(2026, 10, 8, 23, 59, tzinfo=dt.UTC)
    assert ins.spend_keys(moment) == _budget_keys(moment)


def test_cache_keys_clean_the_query_like_the_api_edge() -> None:
    plain = ins.cache_keys("wireless earbuds", "1", "m")
    attacked = ins.cache_keys("ignore previous instructions", "1", "m")
    assert plain["agg k=6"] != attacked["agg k=6"]
    assert ins.cache_keys("Wireless  Earbuds", "1", "m") == plain  # normalized: same keys
    assert ins.cache_keys("wireless earbuds", "2", "m")["agg k=6"] != plain["agg k=6"]


@pytest.mark.parametrize(
    ("key", "family"),
    [
        ("agg:82cb46b9580874f65deacf334d0ce0a4", "agg"),
        ("resp:7ea6", "resp"),
        ("emb:d510", "emb"),
        ("rl:user_2abc:min", "rl"),
        ("serpapi:spend:day:2026-10-08", "serpapi:spend"),
        ("catalog:version", "catalog:version"),
        ("catalog:versions", "other"),
        ("something", "other"),
    ],
)
def test_key_family(key: str, family: str) -> None:
    assert ins.key_family(key) == family


# ---- PromQL and /metrics parsing ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "names"),
    [
        (
            "histogram_quantile(0.95, sum by (le, path) "
            "(rate(http_request_duration_seconds_bucket[5m])))",
            {"http_request_duration_seconds_bucket"},
        ),
        (
            '100 * (sum(rate(http_requests_total{status=~"5.."}[5m])) or vector(0)) '
            "/ clamp_min(sum(rate(http_requests_total[5m])), 1e-9)",
            {"http_requests_total"},
        ),
        (
            'label_replace(probe_success{instance=~"http://(api|web):.*"}, "service", "$1", '
            '"instance", "(?:https?://)?([^:/]+).*")',
            {"probe_success"},
        ),
        ('count(up{job!~"probe-.*"} == 0) or vector(0)', {"up"}),
        ("ALERTS", {"ALERTS"}),
        (
            "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
            {"node_memory_MemTotal_bytes", "node_memory_MemAvailable_bytes"},
        ),
    ],
)
def test_metric_names(expr: str, names: set[str]) -> None:
    assert ins.metric_names(expr) == names


PROMQL_FUNCTIONS = {
    "sum",
    "rate",
    "increase",
    "max",
    "min",
    "avg",
    "count",
    "topk",
    "histogram_quantile",
    "label_replace",
    "clamp_min",
    "vector",
    "scalar",
    "changes",
    "absent",
    "by",
    "without",
    "on",
}


def test_metric_names_on_every_dashboard_query() -> None:
    """Every real panel query yields metric names, never a function or keyword."""
    for make in DASHBOARDS:
        for panel in walk(make().sections):
            for target in panel.targets:
                names = ins.metric_names(target.expr)
                assert names, target.expr
                assert not names & PROMQL_FUNCTIONS, (target.expr, names)


METRICS_PAGE = """\
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/health",status="200"} 3.0
http_requests_total{method="POST",path="/aggregate/stream",status="401"} 2.0
# HELP http_requests_created Total HTTP requests
# TYPE http_requests_created gauge
http_requests_created{method="GET",path="/health",status="200"} 1.79e+09
# HELP serpapi_searches_total Live SerpApi searches actually spent
# TYPE serpapi_searches_total counter
serpapi_searches_total 0.0
# HELP llm_requests_total LLM calls by provider, model and outcome
# TYPE llm_requests_total counter
# HELP http_request_duration_seconds Request latency (s)
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005",path="/health"} 2.0
http_request_duration_seconds_bucket{le="+Inf",path="/health"} 3.0
http_request_duration_seconds_count{path="/health"} 3.0
http_request_duration_seconds_sum{path="/health"} 0.004
"""


def test_parse_samples_keys_values_and_skips_created() -> None:
    samples = ins.parse_samples(METRICS_PAGE)
    assert samples["http_requests_total{method=GET,path=/health,status=200}"] == 3.0
    assert samples["serpapi_searches_total"] == 0.0
    assert not [k for k in samples if "_created" in k]


def test_family_report_tells_zero_from_empty() -> None:
    report = ins.family_report(METRICS_PAGE)
    assert report["http_requests"].series == 2 and report["http_requests"].total == 5.0
    assert report["serpapi_searches"].series == 1 and report["serpapi_searches"].total == 0.0
    assert report["llm_requests"].series == 0  # declared, never touched: empty, not zero
    assert report["http_request_duration_seconds"].kind == "histogram"
    assert report["http_request_duration_seconds"].total == 3.0
    assert "http_requests_created" not in report


def test_group_samples_by_labels() -> None:
    samples = {
        "llm_tokens_total{model=m,provider=groq,type=input}": 900.0,
        "llm_tokens_total{model=m,provider=groq,type=output}": 500.0,
        "llm_tokens_total{model=x,provider=groq,type=input}": 100.0,
        "llm_requests_total{model=m,provider=groq,status=ok}": 2.0,
    }
    assert ins.group_samples(samples, "llm_tokens_total", "provider", "type") == {
        "groq/input": 1000.0,
        "groq/output": 500.0,
    }


# ---- snapshots and the compare -------------------------------------------------------------------


def test_flatten_keeps_numbers_only() -> None:
    assert ins.flatten({"a": {"b": 1, "c": True, "d": "x"}, "e": [1, 2], "f": None}) == {
        "a.b": 1.0,
        "a.c": 1.0,
    }


def test_diff_numbers_reports_changes_and_new_keys() -> None:
    deltas = ins.diff_numbers({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 3.0, "c": 4.0})
    assert [(d.key, d.before, d.after, d.change) for d in deltas] == [
        ("b", 2.0, 3.0, 1.0),
        ("c", None, 4.0, 4.0),
    ]


def test_compare_hides_watcher_traffic_timestamps_and_sums() -> None:
    def state(stream: float, metrics: float, total_s: float, agg: int) -> dict[str, Any]:
        return {
            "taken_at": stream,
            "api": {
                "start_time": 5.0,
                "samples": {
                    "http_requests_total{method=GET,path=/metrics,status=200}": metrics,
                    "http_requests_total{method=POST,path=/aggregate/stream,status=200}": stream,
                    "http_request_duration_seconds_sum{path=/aggregate/stream}": total_s,
                },
            },
            "redis": {"agg": agg},
        }

    sections = ins.compare_sections(state(0, 1, 0.1, 0), state(2, 9, 2.5, 2))
    assert [d.key for d in sections["api"]] == [
        "api.samples.http_requests_total{method=POST,path=/aggregate/stream,status=200}"
    ]
    assert [(d.key, d.change) for d in sections["redis"]] == [("redis.agg", 2.0)]
    assert "taken_at" not in sections


# ---- Jaeger, Langfuse, compose -------------------------------------------------------------------


def _span(
    span_id: str, name: str, parent: str | None, start: int, tags: dict[str, Any] | None = None
) -> dict[str, Any]:
    refs = [{"refType": "CHILD_OF", "spanID": parent}] if parent else []
    return {
        "spanID": span_id,
        "operationName": name,
        "references": refs,
        "startTime": start,
        "duration": 2_500_000 if parent is None else 10,
        "tags": [{"key": k, "value": v} for k, v in (tags or {}).items()],
    }


def test_summarise_trace_finds_root_and_counts_asgi_spans() -> None:
    trace = {
        "traceID": "abc123",
        "spans": [
            _span("c1", "POST /aggregate/stream http receive", "r", 1001),
            _span("r", "POST /aggregate/stream", None, 1000, {"http.status_code": 200}),
            _span("c2", "POST /aggregate/stream http send", "r", 1002),
            _span("c3", "POST /aggregate/stream http send", "r", 1003),
            _span("c4", "recommend.pipeline", "r", 1004),
        ],
    }
    s = ins.summarise_trace(trace)
    assert (s.root, s.spans, s.http_send, s.http_receive) == ("POST /aggregate/stream", 5, 2, 1)
    assert s.inner == ("recommend.pipeline",)
    assert s.duration_ms == 2500.0 and s.status_code == "200" and s.trace_id == "abc123"


@pytest.mark.parametrize(
    ("agent", "client"),
    [
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0", "browser"),
        ("python-httpx/0.28.1", "script"),
        ("testclient", "tests"),
        ("curl/8.9.1", "curl"),
        ("Grafana/13.2.2", "other"),
        ("", "unknown"),
    ],
)
def test_client_of_reads_the_root_user_agent(agent: str, client: str) -> None:
    tags = {"http.user_agent": agent} if agent else {}
    trace = {"spans": [_span("r", "POST /chat", None, 1, tags), _span("c", "x", "r", 2)]}
    assert ins.client_of(trace) == client


def test_price_defined_uses_langfuse_patterns() -> None:
    patterns = [r"(?i)^(openai\/)?(gpt-4o)$", r"(?i)^(claude-sonnet-4-6)$", "[broken("]
    assert ins.price_defined("gpt-4o", patterns)
    assert ins.price_defined("openai/gpt-4o", patterns)
    assert not ins.price_defined("openai/gpt-oss-120b", patterns)


def test_query_has_pii_looks_at_the_query_only() -> None:
    assert ins.query_has_pii({"query": "mail me at someone@example.com", "offers": "x"})
    long_ids = "product_id: 12345678901234567890"  # looks like a card to a regex, isn't user data
    assert not ins.query_has_pii({"query": "wireless earbuds", "offers": long_ids})
    assert not ins.query_has_pii("a plain string input")


def test_published_ports_reads_variable_container_ports() -> None:
    services = {
        "api": {"ports": ["127.0.0.1:${API_PORT:-2011}:${API_PORT:-2011}"]},
        "qdrant": {
            "ports": [
                "127.0.0.1:${QDRANT_HTTP_PORT:-2001}:6333",
                "127.0.0.1:${QDRANT_GRPC_PORT:-2002}:6334",
            ]
        },
        "redis-exporter": {},
    }
    assert ins.published_ports(services, {"API_PORT": "2111"}) == [
        ("api", "API_PORT", 2111),
        ("qdrant", "QDRANT_HTTP_PORT", 2001),
        ("qdrant", "QDRANT_GRPC_PORT", 2002),
    ]


def test_every_compose_port_mapping_is_understood() -> None:
    services = ins.compose_services()
    declared = sum(len((spec or {}).get("ports") or []) for spec in services.values())
    assert len(ins.published_ports(services, {})) == declared


def test_panel_paths_matches_the_generators_own_walk() -> None:
    for make in DASHBOARDS:
        dash = make()
        paths = list(ins.panel_paths(dash.sections))
        assert [p for _, p in paths] == walk(dash.sections)
        assert all(section for section, _ in paths)


# ---- small formatters, the lock, the refusal tokens ---------------------------------------------


@pytest.mark.parametrize(
    ("ms", "text"),
    [
        (-1, "no TTL"),
        (-2, "absent: no such key"),
        (90_000, "1.5 min"),
        (7_200_000, "2.0 h"),
        (2_592_000_000, "30.0 d"),
    ],
)
def test_human_ttl(ms: int, text: str) -> None:
    assert ins.human_ttl(ms) == text


def test_human_bytes() -> None:
    assert ins.human_bytes(512) == "512 B"
    assert ins.human_bytes(1536) == "1.5 KiB"
    assert ins.human_bytes(3 * 1024**3) == "3.0 GiB"


def test_run_lock_is_exclusive_and_never_left_behind(tmp_path: Path) -> None:
    path = tmp_path / "inspect.lock"
    with ins.RunLock(path):
        assert path.exists()
        with pytest.raises(ins.LockBusyError), ins.RunLock(path):
            pass
        assert path.exists()  # the failed second attempt didn't remove the first run's lock
    assert not path.exists()


def test_refusal_tokens() -> None:
    secret = "s" * 40
    labels = [label for label, _ in ins.refusal_tokens(secret, clerk=False)]
    assert "dev token" not in labels  # in dev-auth mode a valid dev token would be ACCEPTED
    tokens = dict(ins.refusal_tokens(secret, clerk=True))
    assert tokens["no token"] is None
    expired = tokens["expired"]
    assert expired is not None
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(expired, secret, algorithms=["HS256"])
    forged = tokens["forged"]
    assert forged is not None
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(forged, secret, algorithms=["HS256"])


def test_ledger_verdict_never_calls_unknown_zero() -> None:
    read = [("SerpApi", 4.0, 4.0), ("tokens", 0.0, 0.0)]
    assert ins.ledger_verdict(read).startswith("nothing was spent")
    assert "not proven" in ins.ledger_verdict([*read, ("Redis day", None, None)])
    moved = ins.ledger_verdict([("SerpApi", 4.0, 5.0), ("Redis day", None, None)])
    assert moved.startswith("something moved") and "SerpApi" in moved
    assert ins.total(None) is None and ins.total({}) == 0


def test_unreachable_names_the_service_and_port() -> None:
    env = load_env()
    ctx = ins.Ctx(
        env=env,
        target="compose",
        cluster="p2",
        http=httpx.Client(),
        redact=ins.Redactor(env),
        verifier=Verifier(env, "p2", live=False),
    )
    ctx.memo["ports"] = {"API_PORT": False, "REDIS_PORT": True}
    message = ins.unreachable(ctx, ("API_PORT", "REDIS_PORT"))
    assert message.startswith(f"not reachable: api (127.0.0.1:{env['API_PORT']})")
    assert "redis" not in message
    assert ins.unreachable(ctx, ("REDIS_PORT",)) == ""
    ctx.target = "kind"  # kind checks don't use compose ports
    assert ins.unreachable(ctx, ("API_PORT",)) == ""


def test_every_needed_port_is_a_known_setting() -> None:
    env = load_env()  # the env spec's defaults, overlaid with .env
    needed = {key for c in ins.REGISTRY for key in c.needs}
    assert needed and needed <= set(env)
    assert all(env[key].isdigit() for key in needed)


def _session(
    *,
    subs: float,
    hits: float,
    misses: float,
    searches: float,
    ok: float,
    no_match: float,
    agg: int,
    items: int | None,
) -> dict[str, Any]:
    """A snapshot after a browser session (the baseline below has every counter at 0)."""
    path = "method=POST,path=/aggregate/stream,status=200"
    samples = {
        f"http_requests_total{{{path}}}": subs,
        "cache_hits_total{layer=aggregate}": hits,
        "cache_misses_total{layer=aggregate}": misses,
        "llm_requests_total{model=m,provider=groq,status=ok}": ok,
        "no_match_total": no_match,
        "guardrail_blocks_total{kind=input_injection}": 1.0,
        "llm_tokens_total{model=m,provider=groq,type=input}": 900.0 * ok,
    }
    return {
        "api": {"start_time": 1.0, "samples": samples},
        "spend": {
            "serpapi_account_used": 4 + searches,
            "redis_day": searches,
            "redis_month": 1 + searches,
            "searches_metric": searches,
        },
        "redis": {"agg": agg, "emb": 4, "resp": 0},
        "qdrant": {"products": 9, "query_cache": 6},
        "dynamodb": None if items is None else {"items": items, "users": 1},
    }


BASELINE = _session(subs=0, hits=0, misses=0, searches=0, ok=0, no_match=0, agg=0, items=None)
BASELINE["api"]["samples"]["guardrail_blocks_total{kind=input_injection}"] = 0.0


def test_battery_report_passes_a_clean_session() -> None:
    now = _session(subs=8, hits=3, misses=5, searches=5, ok=4, no_match=1, agg=5, items=None)
    window = {
        "langfuse": {"generations": 4, "cost": 0.0},
        "jaeger": {"POST /aggregate/stream": {"browser": 8}},
    }
    rows = ins.battery_report(BASELINE, now, window)
    assert [r.check for r in rows if r.verdict != ins.PASS] == []


def test_battery_report_catches_spend_drift_and_history_writes() -> None:
    now = _session(subs=8, hits=3, misses=5, searches=5, ok=4, no_match=1, agg=4, items=2)
    now["spend"]["serpapi_account_used"] += 1  # SerpApi counted a search the app didn't
    rows = {r.check: r for r in ins.battery_report(BASELINE, now, {})}
    assert rows["SerpApi searches: SerpApi's count = Redis day = Redis month = metric"].verdict == (
        ins.FAIL
    )
    assert rows["Discover writes no chat history (DynamoDB items)"].verdict == ins.FAIL
    agg = rows["each search cached its result (agg: keys)"]
    assert agg.verdict == ins.FAIL and "zero offers" in agg.note
    assert rows["Langfuse: one generation per LLM attempt"].verdict == ins.SKIP  # no window data


def test_battery_report_flags_a_restart() -> None:
    now = _session(subs=1, hits=0, misses=1, searches=1, ok=1, no_match=0, agg=1, items=None)
    now["api"]["start_time"] = 2.0
    first = ins.battery_report(BASELINE, now, {})[0]
    assert first.verdict == ins.FAIL and "increase()" in first.note


def test_sum_samples_matches_labels() -> None:
    samples = {
        "cache_hits_total{layer=aggregate}": 3.0,
        "cache_hits_total{layer=catalog_l0}": 9.0,
        "cache_misses_total{layer=aggregate}": 5.0,
    }
    assert ins.sum_samples(samples, "cache_hits_total", layer="aggregate") == 3.0
    assert ins.sum_samples(samples, "cache_hits_total") == 12.0


def test_mask_key_hides_user_ids() -> None:
    assert ins.mask_key("rl:user_2abcdefghijk:day") == "rl:user_2ab…:day"
    assert ins.mask_key("agg:82cb46b9") == "agg:82cb46b9"


def test_clear_refuses_what_is_not_a_cache(capsys: pytest.CaptureFixture[str]) -> None:
    for family in ("rl", "serpapi:spend", "catalog:version"):
        assert ins.main(["--clear", family, "--yes"]) == 2
        assert "refused" in capsys.readouterr().out


def test_registry_names_are_unique_and_grouped() -> None:
    seen = [(c.group, c.name, target) for c in ins.REGISTRY for target in c.targets]
    assert len(seen) == len(set(seen))
    assert {c.group for c in ins.REGISTRY} >= {"services", "api", "auth", "data", "kind"}


def test_langfuse_rows_counts_rows_not_total_items(monkeypatch: pytest.MonkeyPatch) -> None:
    # 2026-10-09: /observations said totalItems 4 for 3 generations, so --compare would have
    # failed "one generation per LLM attempt" on a correct run.
    pages = {
        1: {"data": [{"id": f"g{i}"} for i in range(100)], "meta": {"totalItems": 999}},
        2: {"data": [{"id": "g99"}, {"id": "g100"}], "meta": {"totalItems": 999}},
    }
    calls: list[dict[str, Any]] = []

    def fake_get(ctx: Any, path: str, **params: Any) -> dict[str, Any]:
        calls.append(params)
        return pages[params["page"]]

    monkeypatch.setattr(ins, "langfuse_get", fake_get)
    ctx: Any = None
    rows = ins.langfuse_rows(ctx, "observations", type="GENERATION")
    assert len(rows) == 101  # g0..g100, the repeated g99 once
    assert [c["page"] for c in calls] == [1, 2]
    assert all(c["type"] == "GENERATION" and c["limit"] == 100 for c in calls)


def test_battery_readiness_flags_cached_and_shared_keys() -> None:
    u1 = ins.cache_keys("wireless earbuds", "2", "-", (ins.DISCOVER_K,))[f"agg k={ins.DISCOVER_K}"]
    rows = {r.step: r for r in ins.battery_readiness(lambda k: 60_000 if k == u1 else -2, "2")}
    assert rows["U1"].ttl_ms == 60_000 and not rows["U1"].same_as
    assert rows["U3"].same_as == "U1"  # spacing and case normalise to U1's key
    assert rows["U4"].ttl_ms == -2 and not rows["U4"].same_as
    assert [s for s, r in rows.items() if r.optional] == ["U9", "U14"]


def test_compare_counts_langfuse_rows(capsys: pytest.CaptureFixture[str]) -> None:
    # 2026-10-10: /traces totalItems went 22 -> 27 over a window holding 3 trace rows.
    lf = {"traces": 3, "generations": 3, "models": ["m"], "input_tokens": 9, "output_tokens": 4}
    ins.print_compare(
        {"taken_at": 0.0, "langfuse": {"traces": 22}},
        {"langfuse": {"traces": 27}},
        {"jaeger": {}, "langfuse": {**lf, "cost": 0.0}},
    )
    out = capsys.readouterr().out
    assert "can overcount" in out
    assert "Langfuse traces 3, generations 3" in out
