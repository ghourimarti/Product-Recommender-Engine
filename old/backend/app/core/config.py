"""Typed application configuration.

Replaces the demo's raw ``os.getenv`` access (former ``flipkart/config.py``) with a
single validated settings object. Values are read from environment variables and an
optional ``.env`` file. Nothing is hardcoded; secrets never live in code.

Decision Log: implements D17 (secrets & configuration management).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime ---
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"

    # --- Database (D1) ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/recommender"

    @property
    def sync_database_url(self) -> str:
        """Sync DSN for components that are sync-only (e.g. SQLChatMessageHistory)."""
        return self.database_url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")

    # --- Vector store (D2: Qdrant is the locked target backend) ---
    vector_backend: Literal["astra", "qdrant"] = "qdrant"
    vector_collection_name: str = "flipkart_products"
    embedding_dim: int = Field(default=768, ge=1)  # bge-base-en-v1.5 = 768

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # AstraDB (legacy adapter, retained behind the interface)
    astra_db_api_endpoint: str | None = None
    astra_db_application_token: str | None = None
    astra_db_keyspace: str | None = None

    # --- Embeddings (D5/D12: self-hosted service by default) ---
    embedding_provider: Literal["service", "hf"] = "service"
    embedding_service_url: str = "http://localhost:8001"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    huggingfacehub_api_token: str | None = None

    # --- Retrieval strategy (D3/D6: advanced RAG, all feature-flagged) ---
    retrieval_mode: Literal["dense", "hybrid"] = "hybrid"
    retrieval_fetch_k: int = Field(default=20, ge=1, le=200)  # candidates before rerank
    use_reranker: bool = True
    rerank_top_n: int = Field(default=3, ge=1, le=50)
    sparse_model: str = "Qdrant/bm25"
    reranker_model: str = "ms-marco-MiniLM-L-12-v2"

    # --- Auth (D9: Cognito + provider-agnostic JWT verification) ---
    auth_enabled: bool = True
    jwt_algorithm: Literal["RS256", "HS256"] = "RS256"  # RS256=Cognito, HS256=dev
    jwt_secret: str | None = None  # dev/test HS256 only
    jwt_audience: str | None = None
    jwt_issuer: str | None = None
    cognito_region: str | None = None
    cognito_user_pool_id: str | None = None

    @property
    def cognito_jwks_url(self) -> str | None:
        if self.cognito_region and self.cognito_user_pool_id:
            return (
                f"https://cognito-idp.{self.cognito_region}.amazonaws.com/"
                f"{self.cognito_user_pool_id}/.well-known/jwks.json"
            )
        return None

    # --- Observability (D13/D17) ---
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str | None = None
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Cache (D10) ---
    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = True
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    semantic_cache_max_entries: int = Field(default=1000, ge=1)
    cache_ttl_seconds: int = Field(default=3600, ge=1)
    catalog_version: str = "v1"  # bump on re-index to invalidate cached answers

    # --- Rate limiting + cost controls (D20) ---
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(default=60, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    kill_switch: bool = False  # load-shed: reject new work when on
    budget_enabled: bool = True
    daily_token_budget: int = Field(default=200_000, ge=1)

    # --- LLM tiering + fallback (D4) ---
    groq_api_key: str | None = None
    rag_model: str = "llama-3.1-8b-instant"          # cheap default tier
    rag_model_strong: str = "llama-3.3-70b-versatile"  # escalation tier
    fallback_provider: Literal["openai", "none"] = "openai"
    fallback_model: str = "gpt-4o-mini"               # cross-provider outage fallback
    openai_api_key: str | None = None
    escalate_word_threshold: int = Field(default=30, ge=1)
    rag_temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    retrieval_k: int = Field(default=3, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the env/.env file is parsed once per process."""
    return Settings()


settings = get_settings()
