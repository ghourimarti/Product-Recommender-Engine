"""Write .env and .env.example from ONE layout spec, preserving every value already in .env.

    uv run python ops/env/gen_env.py           # rewrite both files (backs .env up to .env.bak)
    uv run python ops/env/gen_env.py --check   # exit 1 if .env.example is out of date

Layout rules:
  - One boxed section per service; everything that service needs sits together.
  - Documentation sits in the box, above the values. NEVER a trailing comment: python-dotenv
    reads `KEY=   # note` as the value "# note", which is how the old .env.example handed a
    fresh clone a bogus non-empty OPENAI_API_KEY.
  - Host ports are grouped by tier: data 2001-2004, observability 2005-2010 and 2013-2020,
    app 2011-2012. Container ports never change.
  - .env keeps keys the spec doesn't know in a final "not used" section, so no value is lost.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

WIDTH = 76


@dataclass(frozen=True)
class Key:
    name: str
    default: str = ""
    secret: bool = False  # .env.example always ships it empty
    doc: str = ""


@dataclass(frozen=True)
class Section:
    title: str
    subtitle: str = ""
    keys: tuple[Key, ...] = ()
    docs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Tier:
    title: str
    sections: tuple[Section, ...]


SPEC: tuple[Tier, ...] = (
    Tier(
        "DATA STORES  (host ports 2001-2004)",
        (
            Section(
                "QDRANT - vector store (product catalog)",
                "http://localhost:2001/dashboard",
                (
                    Key("QDRANT_HTTP_PORT", "2001"),
                    Key("QDRANT_GRPC_PORT", "2002"),
                    Key(
                        "QDRANT_URL",
                        "http://localhost:2001",
                        doc="host-side URL (make serve); compose uses http://qdrant:6333",
                    ),
                    Key(
                        "QDRANT_API_KEY",
                        secret=True,
                        doc="empty = no auth; set = Qdrant enforces it",
                    ),
                    Key("QDRANT_COLLECTION", "products"),
                ),
            ),
            Section(
                "DYNAMODB LOCAL - chat history",
                "localhost:2003 (no UI; AWS CLI / NoSQL Workbench)",
                (
                    Key("DYNAMODB_PORT", "2003"),
                    Key(
                        "DYNAMODB_ENDPOINT",
                        "http://localhost:2003",
                        doc="empty = real AWS DynamoDB",
                    ),
                    Key("DYNAMODB_TABLE", "p2-recommender"),
                    Key("AWS_REGION", "us-east-1"),
                    Key(
                        "AWS_ACCESS_KEY_ID",
                        secret=True,
                        doc="real AWS only; the emulator gets dummy creds",
                    ),
                    Key("AWS_SECRET_ACCESS_KEY", secret=True),
                ),
            ),
            Section(
                "REDIS - app cache, rate limits, SerpApi budget",
                "localhost:2004 (no auth) - browse it in RedisInsight",
                (
                    Key("REDIS_PORT", "2004"),
                    Key(
                        "REDIS_URL",
                        "redis://localhost:2004/0",
                        doc="host-side URL; compose uses redis://redis:6379/0",
                    ),
                    Key(
                        "REDIS_TIMEOUT_SECONDS",
                        "0.25",
                        doc="fail fast: a Redis outage must not hang requests",
                    ),
                ),
            ),
        ),
    ),
    Tier(
        "APPLICATION  (host ports 2011-2012)",
        (
            Section(
                "API - FastAPI backend",
                "http://localhost:2011/docs",
                (
                    Key("API_PORT", "2011"),
                    Key(
                        "APP_ENV",
                        "local",
                        doc="local | dev | staging | prod; non-local needs CLERK_JWKS_URL",
                    ),
                    Key("LOG_LEVEL", "INFO"),
                    Key("CORS_ORIGINS", "http://localhost:2012,http://localhost:2011"),
                ),
            ),
            Section(
                "WEB - Next.js frontend",
                "http://localhost:2012",
                (
                    Key("WEB_PORT", "2012"),
                    Key(
                        "NEXT_PUBLIC_API_URL",
                        "http://localhost:2011",
                        doc="baked into the browser bundle at BUILD time",
                    ),
                ),
            ),
            Section(
                "CLERK - sign-in (and dev tokens for scripts)",
                "https://dashboard.clerk.com",
                (
                    Key(
                        "CLERK_JWKS_URL",
                        doc="set = API verifies Clerk RS256 tokens; empty = HS256 dev tokens",
                    ),
                    Key("CLERK_PUBLISHABLE_KEY"),
                    Key("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"),
                    Key("CLERK_SECRET_KEY", secret=True),
                    Key(
                        "AUTH_DEV_SECRET",
                        "dev-secret-change-me-in-prod-0123456789abcdef",
                        secret=True,
                        doc="HS256 secret for minted dev tokens (>= 32 bytes)",
                    ),
                    Key(
                        "AUTH_DEV_BYPASS",
                        "false",
                        doc="true + APP_ENV=local + no JWKS = anonymous dev-user",
                    ),
                    Key(
                        "NEXT_PUBLIC_DEV_TOKEN",
                        doc="dev-only token baked into the web bundle; real Clerk tokens win",
                    ),
                ),
            ),
        ),
    ),
    Tier(
        "LLM PROVIDERS + LIVE SHOPPING DATA  (hosted; no ports)",
        (
            Section(
                "GROQ - primary LLM",
                "tried first",
                (
                    Key("GROQ_API_KEY", secret=True),
                    Key("GROQ_MODEL", "openai/gpt-oss-120b"),
                    Key("GROQ_MAX_OUTPUT_TOKENS", "2000"),
                ),
                (
                    "Order: Groq -> OpenAI -> Anthropic; a provider with no key is skipped.",
                    "GROQ_MAX_OUTPUT_TOKENS: gpt-oss reasons before answering; 600 is too few",
                    "Free tier: 8k tokens/min, 1k requests/day; overflow falls back to OpenAI",
                ),
            ),
            Section(
                "OPENAI - fallback LLM + embeddings",
                "embeddings need this key even when Groq answers",
                (
                    Key("OPENAI_API_KEY", secret=True),
                    Key("OPENAI_MODEL", "gpt-4o"),
                    Key("EMBEDDING_MODEL", "text-embedding-3-small"),
                    Key(
                        "EMBEDDING_DIM", "1536", doc="frozen: changing it means re-indexing Qdrant"
                    ),
                ),
            ),
            Section(
                "ANTHROPIC - last-resort LLM",
                "tried when Groq and OpenAI both fail",
                (
                    Key("ANTHROPIC_API_KEY", secret=True),
                    Key("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                ),
            ),
            Section(
                "SERPAPI - live Google Shopping offers (metered: 250 searches/month)",
                "https://serpapi.com/manage-api-key",
                (
                    Key(
                        "SERPAPI_API_KEY",
                        secret=True,
                        doc="required: every aggregate cache miss spends one search",
                    ),
                    Key("SERPAPI_GL", "us", doc="country"),
                    Key("SERPAPI_HL", "en", doc="language"),
                    Key(
                        "SERPAPI_DAILY_BUDGET",
                        "40",
                        doc="global caps for ALL users together; 0 = no cap",
                    ),
                    Key("SERPAPI_MONTHLY_BUDGET", "250"),
                ),
            ),
            Section(
                "COST + SAFETY CONTROLS",
                "",
                (
                    Key(
                        "LLM_ENABLED",
                        "true",
                        doc="false = kill switch: cards still served, no LLM calls",
                    ),
                    Key("MAX_OUTPUT_TOKENS", "600"),
                    Key("RATE_LIMIT_PER_MINUTE", "30", doc="per user"),
                    Key("RATE_LIMIT_PER_DAY", "500", doc="per user"),
                    Key(
                        "MIN_SEMANTIC_SIMILARITY",
                        "0.30",
                        doc="below this the catalog answers 'no good match'",
                    ),
                    Key("CHAT_RETENTION_DAYS", "90", doc="GDPR: TTL on every chat item"),
                ),
            ),
        ),
    ),
    Tier(
        "OBSERVABILITY  (host ports 2005-2010, 2013-2020)",
        (
            Section(
                "JAEGER + OPENTELEMETRY - request traces",
                "http://localhost:2006 (also inside Grafana: Explore > Jaeger)",
                (
                    Key("JAEGER_UI_PORT", "2006"),
                    Key("OTEL_OTLP_GRPC_PORT", "2007"),
                    Key(
                        "OTEL_EXPORTER_OTLP_ENDPOINT",
                        "http://localhost:2007",
                        doc="host-side; compose uses http://jaeger:4317",
                    ),
                    Key("OTEL_SERVICE_NAME", "p2-recommender"),
                    Key("OTEL_SDK_DISABLED", "false"),
                ),
            ),
            Section(
                "PROMETHEUS - metrics + alert rules",
                "http://localhost:2009/targets",
                (Key("PROMETHEUS_PORT", "2009"),),
            ),
            Section(
                "GRAFANA - dashboards (no login: anonymous access)",
                "http://localhost:2010",
                (
                    Key("GRAFANA_PORT", "2010"),
                    Key(
                        "GRAFANA_ANONYMOUS_ROLE",
                        "Admin",
                        doc="Viewer | Editor | Admin; the port is bound to 127.0.0.1",
                    ),
                    Key("GRAFANA_ADMIN_USER", "admin"),
                    Key("GRAFANA_ADMIN_PASSWORD", "admin"),
                ),
            ),
            Section(
                "LANGFUSE - LLM traces, tokens, cost",
                "http://localhost:2019 signs you in; the UI itself is on :2008",
                (
                    Key("LANGFUSE_UI_PORT", "2008"),
                    Key("LANGFUSE_AUTOLOGIN_PORT", "2019"),
                    Key(
                        "LANGFUSE_HOST",
                        "http://localhost:2008",
                        doc="host-side; compose uses http://langfuse-web:3000",
                    ),
                    Key(
                        "LANGFUSE_PUBLIC_KEY",
                        "pk-lf-p2-local",
                        doc="any pk-lf-/sk-lf- pair: Langfuse is bootstrapped WITH these",
                    ),
                    Key("LANGFUSE_SECRET_KEY", "sk-lf-p2-local"),
                    Key(
                        "LANGFUSE_INIT_USER_EMAIL",
                        "admin@example.com",
                        doc="needs a real TLD; @localhost is rejected",
                    ),
                    Key("LANGFUSE_INIT_USER_NAME", "Admin"),
                    Key("LANGFUSE_INIT_USER_PASSWORD", "changeme"),
                    Key("LANGFUSE_NEXTAUTH_SECRET", "langfuse-local-dev-nextauth-secret"),
                    Key("LANGFUSE_SALT", "langfuse-local-dev-salt"),
                    Key(
                        "LANGFUSE_ENCRYPTION_KEY",
                        "0" * 64,
                        doc="64 hex chars; openssl rand -hex 32",
                    ),
                ),
                (
                    "Org, project, user and keys are created on FIRST boot of an empty volume;",
                    "changing them later needs `make downv`.",
                ),
            ),
            Section(
                "POSTGRES - Langfuse metadata database",
                "localhost:2013 (pgAdmin / psql / DBeaver)",
                (
                    Key("LANGFUSE_POSTGRES_PORT", "2013"),
                    Key("LANGFUSE_POSTGRES_USER", "langfuse"),
                    Key("LANGFUSE_POSTGRES_PASSWORD", "langfuse-local-dev"),
                    Key("LANGFUSE_POSTGRES_DB", "langfuse"),
                ),
            ),
            Section(
                "CLICKHOUSE - Langfuse trace store",
                "http://localhost:2014/play (HTTP) - localhost:2015 (native)",
                (
                    Key("LANGFUSE_CLICKHOUSE_HTTP_PORT", "2014"),
                    Key("LANGFUSE_CLICKHOUSE_NATIVE_PORT", "2015"),
                    Key("LANGFUSE_CLICKHOUSE_USER", "langfuse"),
                    Key("LANGFUSE_CLICKHOUSE_PASSWORD", "langfuse-local-dev"),
                ),
            ),
            Section(
                "REDIS - Langfuse queue",
                "localhost:2016 (password below) - browse it in RedisInsight",
                (
                    Key("LANGFUSE_REDIS_PORT", "2016"),
                    Key("LANGFUSE_REDIS_AUTH", "langfuse-local-dev"),
                ),
            ),
            Section(
                "MINIO - Langfuse event + media blobs (S3 API)",
                "http://localhost:2018 (console) - http://localhost:2017 (S3 API)",
                (
                    Key("LANGFUSE_MINIO_API_PORT", "2017"),
                    Key("LANGFUSE_MINIO_CONSOLE_PORT", "2018"),
                    Key("LANGFUSE_MINIO_ROOT_USER", "minio"),
                    Key("LANGFUSE_MINIO_ROOT_PASSWORD", "langfuse-local-dev"),
                ),
            ),
            Section(
                "REDISINSIGHT - Redis GUI, both Redis databases pre-registered",
                "http://localhost:2005",
                (Key("REDISINSIGHT_PORT", "2005"),),
            ),
            Section(
                "CADVISOR - per-container CPU, memory, network",
                "http://localhost:2020 (charts: Grafana > P2 - Containers & health)",
                (Key("CADVISOR_PORT", "2020"),),
            ),
        ),
    ),
)

HEADER = """\
# ============================================================================
#  P2 ProductIQ - environment
# ============================================================================
#  GENERATED by ops/env/gen_env.py: edit the spec there, then re-run it.
#  Values in .env are preserved; only the layout is rewritten.
#
#  Host ports by tier: data 2001-2004 - observability 2005-2010, 2013-2020 -
#  app 2011-2012. Container ports never change, which is why an in-network
#  URL says redis:6379 while a host URL says localhost:2004.
#
#  Every URL:                 make urls
#  URLs + local credentials:  make service_ls
#  Check every component:     make verify
# ============================================================================
"""

EXAMPLE_NOTE = """\
#  This is the TEMPLATE: copy it to .env (`cp .env.example .env`) and fill in the
#  secrets. .env is gitignored; never commit it.
# ============================================================================
"""


def _box(lines: list[str]) -> list[str]:
    bar = "# +" + "-" * (WIDTH - 4) + "+"
    out = [bar]
    for text in lines:
        out.append(f"# | {text:<{WIDTH - 6}} |")
    out.append(bar)
    return out


def _tier_banner(title: str) -> list[str]:
    bar = "# " + "#" * (WIDTH - 2)
    return [bar, f"# ##  {title:<{WIDTH - 8}}##", bar]


def quote(value: str) -> str:
    """A value every reader (python-dotenv, docker compose --env-file, sh) parses identically."""
    if value == "" or re.fullmatch(r"[A-Za-z0-9_./:@,+=\-]+", value):
        return value
    if "'" not in value:
        return f"'{value}'"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render(values: dict[str, str], *, example: bool, extra: dict[str, str] | None = None) -> str:
    out: list[str] = [HEADER.rstrip("\n")]
    if example:
        out[-1] = out[-1].rsplit("\n", 1)[0]  # drop the closing rule; the note closes the header
        out.append(EXAMPLE_NOTE.rstrip("\n"))
    for tier in SPEC:
        out += ["", ""] + _tier_banner(tier.title)
        for section in tier.sections:
            out.append("")
            out += _box([section.title] + ([section.subtitle] if section.subtitle else []))
            documented = [k for k in section.keys if k.doc]
            width = max((len(k.name) for k in documented), default=0)
            for line in section.docs:
                out.append(f"#  {line}")
            for k in documented:
                out.append(f"#  {k.name:<{width}}  {k.doc}")
            for k in section.keys:
                value = (
                    ("" if k.secret else k.default) if example else values.get(k.name, k.default)
                )
                out.append(f"{k.name}={quote(value)}")
    if extra and not example:
        out += ["", ""] + _tier_banner("NOT USED BY P2  (kept so no value is lost)")
        out.append("#  Nothing in P2 reads these. Delete them once you know you don't need them.")
        for name, value in extra.items():
            out.append(f"{name}={quote(value)}")
    return "\n".join(out) + "\n"


def known_keys() -> list[str]:
    return [k.name for tier in SPEC for s in tier.sections for k in s.keys]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if .env.example is stale")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    env_path, example_path = args.root / ".env", args.root / ".env.example"

    example = render({}, example=True)
    if args.check:
        current = example_path.read_text(encoding="utf-8") if example_path.exists() else ""
        if current != example:
            print(".env.example is out of date: run `uv run python ops/env/gen_env.py`")
            return 1
        print(".env.example is up to date")
        return 0

    example_path.write_text(example, encoding="utf-8", newline="\n")
    print(f"wrote {example_path} ({len(known_keys())} keys)")
    if not env_path.exists():
        print(
            f"no {env_path}: copy the template with `cp .env.example .env` and fill in the secrets"
        )
        return 0

    old = {k: (v or "") for k, v in dotenv_values(env_path).items()}
    known = set(known_keys())
    extra = {k: v for k, v in old.items() if k not in known}
    text = render(old, example=False, extra=extra)
    shutil.copy2(env_path, env_path.with_name(".env.bak"))
    env_path.write_text(text, encoding="utf-8", newline="\n")

    new = {k: (v or "") for k, v in dotenv_values(env_path).items()}
    lost = sorted(k for k in old if k not in new)
    changed = sorted(k for k in old if k in new and old[k] != new[k])
    added = sorted(k for k in new if k not in old)
    print(f"wrote {env_path}: {len(new)} keys; backup at .env.bak")
    print(f"  values preserved: {len(old) - len(lost) - len(changed)}/{len(old)}")
    print(f"  added with defaults: {added}")
    print(f"  kept under 'not used': {sorted(extra)}")
    if lost or changed:
        print(
            f"  ERROR lost={lost} changed={changed}: restore with `cp .env.bak .env`",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
