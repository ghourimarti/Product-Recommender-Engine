"""Typed application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from .env locally, Secrets Manager in prod."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # LLM tiering: Groq primary -> OpenAI escalation -> Anthropic fallback.
    groq_model: str = "llama-3.3-70b-versatile"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-6"

    # Ports live in the 2000-range, sequenced by boot order (see .env.example).
    # Storage tier:  2001 qdrant-http, 2002 qdrant-grpc, 2003 dynamodb, 2004 redis.
    qdrant_url: str = "http://localhost:2001"
    qdrant_api_key: str = ""
    qdrant_collection: str = "products"

    reranker_model: str = "BAAI/bge-reranker-base"  # cross-encoder reranker, runs locally
    rerank_enabled: bool = False  # off by default; regressed NDCG@3/Recall@3 in evaluation

    # "No good match" gate. Absolute dense-cosine floor: below this, the catalog simply
    # cannot answer the query, so we return no_match instead of confidently recommending
    # irrelevant products. Measured on this catalog: on-topic 0.47-0.55, off-topic 0.04-0.17.
    min_semantic_similarity: float = 0.30

    # Same "no good match" idea for the live aggregator: Google returns *something* for any
    # string, so gibberish yields confident-but-irrelevant offers. Reject when the best offer is
    # semantically unrelated to the query. Measured on real offers: valid queries 0.31-0.51,
    # gibberish 0.18-0.19 -> 0.25 separates them. 0 disables the gate.
    min_aggregate_similarity: float = 0.25

    # Primary DB: DynamoDB. Local uses DynamoDB-local + dummy creds.
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    dynamodb_endpoint: str = "http://localhost:2003"
    dynamodb_table: str = "p2-recommender"
    # GDPR retention: written as a `ttl` attribute on every chat item; DynamoDB
    # expires them automatically. Without the attribute the table's TTL setting does nothing.
    chat_retention_days: int = 90

    # Cache + queue broker: Redis.
    redis_url: str = "redis://localhost:2004/0"
    # Redis is on the hot path (cache + rate limiter). Without a socket timeout a Redis outage
    # hangs the request (measured: 24.7s) instead of failing fast, so every worker blocks and a
    # cache outage becomes a full outage. Fail fast, then degrade.
    redis_timeout_seconds: float = 0.25

    # Auth. With clerk_jwks_url set -> verify Clerk RS256 tokens; else dev HS256.
    clerk_jwks_url: str = ""
    auth_dev_secret: str = "dev-secret-change-me-in-prod-0123456789abcdef"  # >=32B (HS256)
    rate_limit_per_minute: int = 30
    rate_limit_per_day: int = 500

    # Unauthenticated requests are rejected by default (fail closed). The dev bypass, which
    # grants an anonymous caller the `dev-user` identity, must be opted into explicitly and is
    # only honoured when app_env == "local". Without this, an empty CLERK_JWKS_URL in a deployed
    # environment would silently make the API public and collapse every caller into one shared
    # identity (i.e. shared chat history). See `require_user` / `assert_auth_config_sane`.
    auth_dev_bypass: bool = False

    # Observability. All optional; telemetry degrades gracefully if unset.
    # OTLP receiver host port = 2007; Langfuse host port = 2008 (see .env.example).
    otel_exporter_otlp_endpoint: str = ""  # e.g. http://localhost:2007 (Jaeger/collector)
    otel_service_name: str = "p2-recommender"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Security + cost controls.
    app_env: str = "local"  # local | dev | staging | prod - gates the auth dev-bypass
    log_level: str = "INFO"
    llm_enabled: bool = True  # kill-switch: false -> serve cached recs, skip LLM explanations
    max_output_tokens: int = 600

    # Global SerpApi budget guard. SerpApi is metered (free plan = 250/month), so a
    # single user could otherwise drain the whole quota. 0 disables the cap.
    serpapi_monthly_budget: int = 250
    serpapi_daily_budget: int = 40

    # Live shopping source: SerpApi (Google Shopping). Aggregator data + buy links.
    serpapi_api_key: str = ""
    serpapi_gl: str = "us"  # country
    serpapi_hl: str = "en"  # language
    # CORS allow-list for the browser frontend (locked to known origins).
    # 2012 = web port, 2011 = api port (self-origin for /health probes, etc.).
    cors_origins: str = "http://localhost:2012,http://localhost:2011"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
