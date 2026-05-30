"""Step 12: JWT auth (HS256 dev path) + protected routes + RBAC."""
from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_service
from app.core.config import settings
from app.core.security import HSVerifier, _principal_from_claims
from app.main import create_app
from tests.conftest import FakeRagService

SECRET = "test-secret-at-least-32-bytes-long-for-hmac-sha256"


def _token(claims: dict) -> str:
    return jwt.encode(claims, SECRET, algorithm="HS256")


@pytest.fixture
def auth_client(monkeypatch) -> TestClient:
    import fakeredis

    from app.api.deps import get_budget, get_limiter
    from app.core.budget import TokenBudget
    from app.core.rate_limiter import RateLimiter

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    monkeypatch.setattr(settings, "jwt_audience", None)
    app = create_app()
    app.state.rag_service = FakeRagService(ready=True)
    app.dependency_overrides[get_rag_service] = lambda: app.state.rag_service
    shared = fakeredis.FakeRedis()
    app.dependency_overrides[get_limiter] = lambda: RateLimiter(shared)
    app.dependency_overrides[get_budget] = lambda: TokenBudget(shared)
    return TestClient(app, raise_server_exceptions=False)


def test_verifier_and_principal_extraction():
    claims = HSVerifier().verify  # ensure callable
    assert callable(claims)
    p = _principal_from_claims({"sub": "u1", "email": "a@b.com", "cognito:groups": ["admin"]})
    assert p.sub == "u1" and p.email == "a@b.com" and "admin" in p.roles


def test_chat_requires_token(auth_client):
    r = auth_client.post("/chat", json={"message": "hi"})
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"


def test_chat_accepts_valid_token(auth_client):
    token = _token({"sub": "user-9", "email": "u@x.com"})
    r = auth_client.post("/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_chat_rejects_garbage_token(auth_client):
    r = auth_client.post("/chat", json={"message": "hi"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401
