"""Unit tests for JWT auth (Step 10). Dev HS256 mode; no Clerk/network."""

from __future__ import annotations

import pytest

from core.auth import AuthError, decode_token, mint_dev_token, user_id_from_token
from core.config import Settings


def _settings(secret: str = "test-secret") -> Settings:
    return Settings(clerk_jwks_url="", auth_dev_secret=secret)


def test_mint_and_decode_roundtrip() -> None:
    settings = _settings()
    token = mint_dev_token("user-123", settings)
    assert user_id_from_token(token, settings) == "user-123"


def test_garbage_token_raises() -> None:
    with pytest.raises(AuthError):
        decode_token("not.a.valid.token", _settings())


def test_wrong_secret_rejected() -> None:
    token = mint_dev_token("u", _settings("secret-a"))
    with pytest.raises(AuthError):
        decode_token(token, _settings("secret-b"))
