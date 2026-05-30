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

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "products"

    reranker_model: str = "BAAI/bge-reranker-base"  # cross-encoder (Decision 3), runs locally
    rerank_enabled: bool = False  # A/B showed it regressed NDCG@3/Recall@3 — off by default

    # Primary DB: DynamoDB (Decision 1). Local uses DynamoDB-local + dummy creds.
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    dynamodb_endpoint: str = "http://localhost:8000"
    dynamodb_table: str = "p2-recommender"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
