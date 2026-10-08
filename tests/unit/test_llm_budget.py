"""Each provider gets the right max_tokens: Groq's gpt-oss needs room to reason first."""

from __future__ import annotations

from core.config import Settings
from core.llm import _make_model


def _settings() -> Settings:
    return Settings(
        groq_api_key="gsk-test",
        openai_api_key="sk-test",
        anthropic_api_key="sk-ant-test",
        max_output_tokens=600,
        groq_max_output_tokens=2000,
    )


def test_groq_gets_its_own_budget() -> None:
    assert _make_model("groq", _settings()).max_tokens == 2000


def test_other_providers_keep_the_cost_cap() -> None:
    assert _make_model("openai", _settings()).max_tokens == 600
    assert _make_model("anthropic", _settings()).max_tokens == 600


def test_default_groq_model_is_one_groq_still_serves() -> None:
    # llama-3.3-70b-versatile was retired on Groq (404 model_not_found, 2026-10-08).
    assert Settings().groq_model == "openai/gpt-oss-120b"
