"""Step 1 smoke tests: typed config loads and validates without secrets in code."""
from __future__ import annotations

import importlib


def test_settings_defaults(monkeypatch):
    # No env set -> safe defaults, secrets are None (never hardcoded).
    for var in ("ASTRA_DB_API_ENDPOINT", "GROQ_API_KEY", "HUGGINGFACEHUB_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)

    import app.core.config as config
    importlib.reload(config)
    s = config.Settings(_env_file=None)

    assert s.embedding_model == "BAAI/bge-base-en-v1.5"
    assert s.rag_model == "llama-3.1-8b-instant"
    assert s.retrieval_k == 3
    assert s.groq_api_key is None  # secret comes from env, not code


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-123")
    monkeypatch.setenv("RETRIEVAL_K", "7")

    import app.core.config as config
    s = config.Settings(_env_file=None)

    assert s.groq_api_key == "test-key-123"
    assert s.retrieval_k == 7


def test_retrieval_k_bounds():
    import pytest
    from pydantic import ValidationError

    import app.core.config as config
    with pytest.raises(ValidationError):
        config.Settings(_env_file=None, retrieval_k=999)
