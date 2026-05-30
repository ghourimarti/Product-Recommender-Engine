"""Step 15: tiering decision logic + fallback assembly."""
from __future__ import annotations

from app.core.config import settings
from app.rag.llm_router import build_tier_model, select_tier, should_escalate


def test_should_escalate_on_comparative_or_long():
    assert should_escalate("compare the BoAt vs the Sony earbuds") is True
    assert should_escalate("which is better for bass") is True
    assert should_escalate("battery life?") is False


def test_select_tier():
    assert select_tier("battery life?", kill_switch=False) == "cheap"
    assert select_tier("compare X vs Y", kill_switch=False) == "strong"
    # kill-switch forces cheap even for complex queries (cost control)
    assert select_tier("compare X vs Y", kill_switch=True) == "cheap"


class _FakeModel:
    def __init__(self, name, provider):
        self.name, self.provider, self.fallbacks = name, provider, None

    def with_fallbacks(self, others):
        self.fallbacks = others
        return self


def test_build_tier_model_attaches_fallback(monkeypatch):
    monkeypatch.setattr(settings, "fallback_provider", "openai")
    built = []

    def fake_builder(name, provider="groq"):
        m = _FakeModel(name, provider)
        built.append(m)
        return m

    model = build_tier_model("strong", model_builder=fake_builder)
    assert model.name == settings.rag_model_strong and model.provider == "groq"
    assert model.fallbacks is not None and model.fallbacks[0].provider == "openai"


def test_build_tier_model_no_fallback(monkeypatch):
    monkeypatch.setattr(settings, "fallback_provider", "none")

    def fake_builder(name, provider="groq"):
        return _FakeModel(name, provider)

    model = build_tier_model("cheap", model_builder=fake_builder)
    assert model.name == settings.rag_model and model.fallbacks is None
