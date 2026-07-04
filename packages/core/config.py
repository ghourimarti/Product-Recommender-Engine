"""Typed application settings (Decision 17), loaded from environment / .env."""

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

    # LLM tiering (Decision 4): Groq primary -> OpenAI escalation -> Anthropic fallback.
    groq_model: str = "llama-3.3-70b-versatile"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-6"

    # Ports live in the 2000-range, sequenced by boot order (see .env.example).
    # Storage tier:  2001 qdrant-http, 2002 qdrant-grpc, 2003 dynamodb, 2004 redis.
    qdrant_url: str = "http://localhost:2001"
    qdrant_api_key: str = ""
    qdrant_collection: str = "products"

    reranker_model: str = "BAAI/bge-reranker-base"  # cross-encoder (Decision 3), runs locally
    rerank_enabled: bool = False  # A/B showed it regressed NDCG@3/Recall@3 — off by default

    # Primary DB: DynamoDB (Decision 1). Local uses DynamoDB-local + dummy creds.
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    dynamodb_endpoint: str = "http://localhost:2003"
    dynamodb_table: str = "p2-recommender"

    # Cache + queue broker: Redis (Decisions 10, 11).
    redis_url: str = "redis://localhost:2004/0"

    # Auth (Decision 9). With clerk_jwks_url set -> verify Clerk RS256 tokens; else dev HS256.
    clerk_jwks_url: str = ""
    auth_dev_secret: str = "dev-secret-change-me-in-prod-0123456789abcdef"  # >=32B (HS256)
    rate_limit_per_minute: int = 30
    rate_limit_per_day: int = 500

    # Observability (Decision 13). All optional — telemetry degrades gracefully if unset.
    # OTLP receiver host port = 2007; Langfuse host port = 2008 (see .env.example).
    otel_exporter_otlp_endpoint: str = ""  # e.g. http://localhost:2007 (Jaeger/collector)
    otel_service_name: str = "p2-recommender"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Security + cost controls (Decisions 18, 20).
    llm_enabled: bool = True  # kill-switch: false -> serve cached recs, skip LLM explanations
    max_output_tokens: int = 600
    # CORS allow-list for the browser frontend (Decision 18: locked to known origins).
    # 2012 = web port, 2011 = api port (self-origin for /health probes, etc.).
    cors_origins: str = "http://localhost:2012,http://localhost:2011"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
