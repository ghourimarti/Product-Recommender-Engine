"""Every P2 component in one list: where it lives, how to sign in, and whether it is running.

`make urls`, `make service_ls` and `make verify` all read this list. Ports and logins come from
.env, falling back to the defaults in ops/env/gen_env.py, so a change there reaches every printout.

Third-party keys (PROVIDER_SECRETS) are never printed: `make service_ls` shows "set" or "missing".
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from ops.env.gen_env import SPEC

ROOT = Path(__file__).resolve().parents[2]

PROVIDER_SECRETS = frozenset(
    {
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "ANTHROPIC_API_KEY",
        "SERPAPI_API_KEY",
        "CLERK_SECRET_KEY",
        "COHERE_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
    }
)

KIND_LABEL = "io.x-k8s.kind.cluster"
KPS = "svc/kube-prometheus-stack"


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """The spec's defaults, overlaid with whatever .env sets."""
    env = {
        key.name: key.default for tier in SPEC for section in tier.sections for key in section.keys
    }
    if path.exists():
        env.update({k: v or "" for k, v in dotenv_values(path).items()})
    return env


def run(cmd: Sequence[str], timeout: float = 30) -> subprocess.CompletedProcess[str] | None:
    """Run a command and capture its output; None when the tool is missing or hangs."""
    if shutil.which(cmd[0]) is None:
        return None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def running_containers() -> set[str] | None:
    """Names of the running containers, or None when Docker can't be reached."""
    res = run(["docker", "ps", "--format", "{{.Names}}"])
    if res is None or res.returncode != 0:
        return None
    return set(res.stdout.split())


@dataclass(frozen=True)
class KindState:
    cluster: str
    nodes: dict[str, str] = field(default_factory=dict)  # node container -> docker state

    @property
    def exists(self) -> bool:
        return bool(self.nodes)

    @property
    def running(self) -> bool:
        return self.exists and all(state == "running" for state in self.nodes.values())

    @property
    def label(self) -> str:
        if not self.exists:
            return "absent"
        up = sum(state == "running" for state in self.nodes.values())
        return "running" if self.running else f"stopped ({up}/{len(self.nodes)} nodes up)"


def kind_clusters() -> dict[str, KindState]:
    """Every kind cluster on this Docker, read from the node containers' labels."""
    fmt = '{{.Label "' + KIND_LABEL + '"}} {{.Names}} {{.State}}'
    res = run(["docker", "ps", "-a", "--filter", f"label={KIND_LABEL}", "--format", fmt])
    clusters: dict[str, KindState] = {}
    if res is None or res.returncode != 0:
        return clusters
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            name, node, state = parts
            clusters.setdefault(name, KindState(name)).nodes[node] = state
    return clusters


# Optional add-ons, recognised by a Service each one installs. The monitoring namespace alone
# proves nothing: the lean cluster creates it too.
ADDON_SERVICES = {
    "argocd": ("argocd", "argocd-server"),
    "monitoring": ("monitoring", "kube-prometheus-stack-grafana"),
}


def kind_addons(context: str) -> set[str]:
    """Which optional add-ons (argocd, monitoring) a running cluster has."""
    res = run(
        ["kubectl", "--context", context, "--request-timeout=5s", "get", "svc", "-A", "-o", "json"]
    )
    if res is None or res.returncode != 0:
        return set()
    present = {
        (s["metadata"]["namespace"], s["metadata"]["name"]) for s in json.loads(res.stdout)["items"]
    }
    return {addon for addon, svc in ADDON_SERVICES.items() if svc in present}


def kind_secret_value(context: str, namespace: str, name: str, key: str) -> str | None:
    """One decoded value of a Secret in the cluster (local admin passwords only)."""
    jsonpath = "{.data." + key.replace(".", "\\.") + "}"
    res = run(
        [
            "kubectl",
            "--context",
            context,
            "-n",
            namespace,
            "get",
            "secret",
            name,
            "-o",
            f"jsonpath={jsonpath}",
        ]
    )
    if res is None or res.returncode != 0 or not res.stdout:
        return None
    return base64.b64decode(res.stdout).decode()


# ---- the catalog ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Link:
    target: str
    note: str = ""


@dataclass(frozen=True)
class Item:
    name: str
    container: str | None  # its status; None = not a container (a hosted API, a command)
    links: tuple[Link, ...] = ()
    creds: tuple[tuple[str, str], ...] = ()  # shown only by `make service_ls`
    key: str = ""  # hosted providers: the .env key whose presence is the status


@dataclass(frozen=True)
class Group:
    title: str
    items: tuple[Item, ...]
    footer: tuple[str, ...] = ()  # shown only by `make service_ls`


def _secret_state(env: Mapping[str, str], key: str) -> str:
    return "set (not printed)" if env.get(key) else "MISSING"


def compose_groups(env: Mapping[str, str]) -> list[Group]:
    """The compose stack (make up), app first, then its stores, then what watches them."""
    e = env
    api = f"http://localhost:{e['API_PORT']}"
    dev_tokens = (
        "off: CLERK_JWKS_URL is set, so the API accepts Clerk tokens only"
        if e.get("CLERK_JWKS_URL")
        else f"on: HS256 tokens signed with AUTH_DEV_SECRET={e.get('AUTH_DEV_SECRET', '')}"
    )
    pg_uri = (
        f"postgresql://{e['LANGFUSE_POSTGRES_USER']}:{e['LANGFUSE_POSTGRES_PASSWORD']}"
        f"@localhost:{e['LANGFUSE_POSTGRES_PORT']}/{e['LANGFUSE_POSTGRES_DB']}"
    )
    return [
        Group(
            "APP",
            (
                Item(
                    "Web app (Next.js)",
                    "p2-web",
                    (Link(f"http://localhost:{e['WEB_PORT']}", "sign in with Clerk, then chat"),),
                    (
                        ("sign-in", "your Clerk account (Sign up on the page creates one)"),
                        ("Clerk keys", "dashboard.clerk.com > your app > API keys"),
                        ("secret key", _secret_state(e, "CLERK_SECRET_KEY")),
                    ),
                ),
                Item(
                    "API (FastAPI)",
                    "p2-api",
                    (
                        Link(f"{api}/docs", "Swagger; routes other than /health need a token"),
                        Link(f"{api}/health"),
                        Link(f"{api}/metrics", "raw Prometheus metrics"),
                    ),
                    (
                        (
                            "auth",
                            "Bearer <Clerk session token> (DevTools > Network on the web app)",
                        ),
                        ("dev tokens", dev_tokens),
                        ("dev bypass", f"AUTH_DEV_BYPASS={e.get('AUTH_DEV_BYPASS', 'false')}"),
                    ),
                ),
            ),
        ),
        Group(
            "DATA STORES",
            (
                Item(
                    "Qdrant (catalog vectors)",
                    "p2-qdrant",
                    (
                        Link(f"http://localhost:{e['QDRANT_HTTP_PORT']}/dashboard"),
                        Link(f"localhost:{e['QDRANT_GRPC_PORT']}", "gRPC"),
                    ),
                    (
                        ("api key", e.get("QDRANT_API_KEY") or "(none: open access)"),
                        ("collection", e["QDRANT_COLLECTION"]),
                    ),
                ),
                Item(
                    "DynamoDB local (chats)",
                    "p2-dynamodb",
                    (
                        Link(
                            f"http://localhost:{e['DYNAMODB_PORT']}",
                            "no UI: AWS CLI / NoSQL Workbench",
                        ),
                    ),
                    (
                        ("region", e["AWS_REGION"]),
                        ("access key", "local   (any value works: -sharedDb)"),
                        ("secret key", "local"),
                        ("table", e["DYNAMODB_TABLE"]),
                        (
                            "list",
                            f"aws dynamodb scan --table-name {e['DYNAMODB_TABLE']} --endpoint-url "
                            f"http://localhost:{e['DYNAMODB_PORT']} --region {e['AWS_REGION']}",
                        ),
                    ),
                ),
                Item(
                    "Redis (app cache)",
                    "p2-redis",
                    (Link(f"localhost:{e['REDIS_PORT']}", "browse in RedisInsight"),),
                    (("password", "(none)"), ("cli", "docker exec -it p2-redis redis-cli")),
                ),
            ),
        ),
        Group(
            "OBSERVABILITY",
            (
                Item(
                    "Grafana (dashboards)",
                    "p2-grafana",
                    (
                        Link(
                            f"http://localhost:{e['GRAFANA_PORT']}",
                            "no login; folder P2 has 5 boards",
                        ),
                    ),
                    (
                        ("access", f"anonymous {e['GRAFANA_ANONYMOUS_ROLE']} (no login needed)"),
                        ("admin user", e["GRAFANA_ADMIN_USER"]),
                        ("admin pass", e["GRAFANA_ADMIN_PASSWORD"]),
                    ),
                ),
                Item(
                    "Prometheus",
                    "p2-prometheus",
                    (
                        Link(
                            f"http://localhost:{e['PROMETHEUS_PORT']}/targets",
                            "every scrape + probe",
                        ),
                        Link(f"http://localhost:{e['PROMETHEUS_PORT']}/alerts", "11 alert rules"),
                    ),
                    (("auth", "(none)"),),
                ),
                Item(
                    "Jaeger (request traces)",
                    "p2-jaeger",
                    (
                        Link(
                            f"http://localhost:{e['JAEGER_UI_PORT']}",
                            f"service {e['OTEL_SERVICE_NAME']}",
                        ),
                        Link(f"localhost:{e['OTEL_OTLP_GRPC_PORT']}", "OTLP gRPC receiver"),
                    ),
                    (("auth", "(none)"),),
                ),
                Item(
                    "Langfuse (LLM traces, cost)",
                    "p2-langfuse-autologin",  # the front door that serves the port
                    (
                        Link(
                            f"http://localhost:{e['LANGFUSE_UI_PORT']}", "opens signed in, no login"
                        ),
                    ),
                    (
                        ("login", "automatic (the form never shows); for the SDK or API:"),
                        ("email", e["LANGFUSE_INIT_USER_EMAIL"]),
                        ("password", e["LANGFUSE_INIT_USER_PASSWORD"]),
                        ("org / proj", "p2-recommender-org / p2-recommender-project"),
                        ("public key", e["LANGFUSE_PUBLIC_KEY"]),
                        ("secret key", e["LANGFUSE_SECRET_KEY"]),
                    ),
                ),
                Item(
                    "RedisInsight",
                    "p2-redisinsight",
                    (
                        Link(
                            f"http://localhost:{e['REDISINSIGHT_PORT']}",
                            "both Redis DBs pre-registered",
                        ),
                    ),
                    (("auth", "(none)"),),
                ),
                Item(
                    "cAdvisor (containers)",
                    "p2-cadvisor",
                    (Link(f"http://localhost:{e['CADVISOR_PORT']}/containers/"),),
                    (("auth", "(none)"),),
                ),
            ),
            footer=(
                "Exporters (no UI; Prometheus scrapes them): redis, langfuse-redis, postgres,",
                "blackbox (HTTP/TCP probes of every service).",
            ),
        ),
        Group(
            "LANGFUSE STORES",
            (
                Item(
                    "Postgres (Langfuse)",
                    "p2-langfuse-postgres",
                    (Link(f"localhost:{e['LANGFUSE_POSTGRES_PORT']}", "pgAdmin / psql / DBeaver"),),
                    (
                        ("host", "localhost"),
                        ("port", e["LANGFUSE_POSTGRES_PORT"]),
                        ("database", e["LANGFUSE_POSTGRES_DB"]),
                        ("user", e["LANGFUSE_POSTGRES_USER"]),
                        ("password", e["LANGFUSE_POSTGRES_PASSWORD"]),
                        ("uri", pg_uri),
                    ),
                ),
                Item(
                    "ClickHouse (Langfuse traces)",
                    "p2-langfuse-clickhouse",
                    (
                        Link(
                            f"http://localhost:{e['LANGFUSE_CLICKHOUSE_HTTP_PORT']}/play",
                            "SQL in the browser",
                        ),
                        Link(
                            f"localhost:{e['LANGFUSE_CLICKHOUSE_NATIVE_PORT']}", "native protocol"
                        ),
                    ),
                    (
                        ("user", e["LANGFUSE_CLICKHOUSE_USER"]),
                        ("password", e["LANGFUSE_CLICKHOUSE_PASSWORD"]),
                        ("database", "default"),
                    ),
                ),
                Item(
                    "Redis (Langfuse queue)",
                    "p2-langfuse-redis",
                    (Link(f"localhost:{e['LANGFUSE_REDIS_PORT']}", "browse in RedisInsight"),),
                    (("password", e["LANGFUSE_REDIS_AUTH"]),),
                ),
                Item(
                    "MinIO (Langfuse blobs)",
                    "p2-langfuse-minio",
                    (
                        Link(f"http://localhost:{e['LANGFUSE_MINIO_CONSOLE_PORT']}", "console"),
                        Link(f"http://localhost:{e['LANGFUSE_MINIO_API_PORT']}", "S3 API"),
                    ),
                    (
                        ("user", e["LANGFUSE_MINIO_ROOT_USER"]),
                        ("password", e["LANGFUSE_MINIO_ROOT_PASSWORD"]),
                        ("bucket", "langfuse"),
                    ),
                ),
            ),
            footer=(
                "P2 keeps no data in Postgres: chats live in DynamoDB, the catalog in Qdrant,",
                "caches in Redis. Langfuse's Postgres is the only Postgres in the stack.",
            ),
        ),
    ]


def model_group(env: Mapping[str, str]) -> Group:
    """Hosted LLMs, tried in order, and the small models the API runs on its own CPU."""
    e = env
    return Group(
        "LLM + MODELS (hosted chain; no local GPU engine)",
        (
            Item("1. Groq (tried first)", None, (Link(e["GROQ_MODEL"]),), key="GROQ_API_KEY"),
            Item("2. OpenAI (fallback)", None, (Link(e["OPENAI_MODEL"]),), key="OPENAI_API_KEY"),
            Item(
                "3. Anthropic (last)", None, (Link(e["ANTHROPIC_MODEL"]),), key="ANTHROPIC_API_KEY"
            ),
            Item(
                "Embeddings (OpenAI)",
                None,
                (Link(e["EMBEDDING_MODEL"], f"{e['EMBEDDING_DIM']} dims, every query + the seed"),),
                key="OPENAI_API_KEY",
            ),
            Item(
                "SerpApi (live offers)",
                None,
                (Link("Google Shopping", "metered"),),
                key="SERPAPI_API_KEY",
            ),
            Item(
                "BM25 sparse (local)",
                "p2-api",
                (Link("Qdrant/bm25", "fastembed, inside the API, CPU"),),
            ),
        ),
        footer=(
            f"LLM_ENABLED={e.get('LLM_ENABLED', 'true')}; SerpApi budget "
            f"{e.get('SERPAPI_DAILY_BUDGET')}/day, {e.get('SERPAPI_MONTHLY_BUDGET')}/month",
            "Which provider answered: Grafana > P2 - API & LLM > 'LLM calls by provider',",
            "or Langfuse > Traces > a trace > its generation (model, tokens, cost).",
            "[key ] = the key is set, not that it works: make verify LIVE=1 calls each provider.",
            "Provider keys are never printed; they live in .env.",
        ),
    )


def kind_group(
    cluster: str,
    state: KindState,
    addons: set[str],
    passwords: Mapping[str, str | None] | None = None,
) -> Group:
    """The kind cluster (make up starts it, make down stops it)."""
    ctx = f"kubectl --context kind-{cluster}"
    passwords = passwords or {}
    items = [
        Item(
            "App via Envoy Gateway",
            None,
            (
                Link("http://app.localhost", "same Clerk sign-in"),
                Link("https://app.localhost", "local CA (cert-manager)"),
                Link("http://app.localhost/api/health"),
            ),
        ),
        Item(
            "Pods",
            None,
            (Link(f"{ctx} -n p2 get pods"),),
            (("secret", "Secret p2/p2-secrets, an allow-list of .env (make kind-secret)"),),
        ),
        Item(
            "Qdrant (in-cluster)",
            None,
            (
                Link(
                    f"{ctx} -n p2 port-forward svc/qdrant 6333:6333",
                    "then localhost:6333/dashboard",
                ),
            ),
            (("api key", "same QDRANT_API_KEY as above"),),
        ),
        Item("Redis (in-cluster)", None, (Link(f"{ctx} -n p2 port-forward svc/redis 6379:6379"),)),
        Item(
            "DynamoDB (in-cluster)",
            None,
            (Link(f"{ctx} -n p2 port-forward svc/dynamodb 8000:8000"),),
        ),
    ]
    if "argocd" in addons:
        items.append(
            Item(
                "Argo CD (GitOps)",
                None,
                (
                    Link(
                        f"{ctx} -n argocd port-forward svc/argocd-server 8080:80",
                        "then localhost:8080",
                    ),
                ),
                (
                    ("access", "anonymous read-only"),
                    ("admin user", "admin"),
                    (
                        "admin pass",
                        passwords.get("argocd") or "Secret argocd/argocd-initial-admin-secret",
                    ),
                ),
            )
        )
    if "monitoring" in addons:
        items.append(
            Item(
                "Grafana (in-cluster)",
                None,
                (
                    Link(
                        f"{ctx} -n monitoring port-forward {KPS}-grafana 3000:80",
                        "then localhost:3000",
                    ),
                    Link(f"{ctx} -n monitoring port-forward {KPS}-prometheus 9090:9090"),
                ),
                (
                    ("access", "anonymous read-only"),
                    ("admin user", "admin"),
                    (
                        "admin pass",
                        passwords.get("grafana")
                        or "Secret monitoring/kube-prometheus-stack-grafana",
                    ),
                ),
            )
        )
    footer: tuple[str, ...] = ()
    if "monitoring" not in addons:
        footer = (
            "Lean cluster: no in-cluster Prometheus/Grafana. make kind-addons-monitoring adds",
            "them (~1.3 GB); the compose Grafana above watches the compose stack.",
        )
    return Group(f"KUBERNETES - kind cluster '{cluster}' ({state.label})", tuple(items), footer)
