"""JWT authentication.

Two verification modes, chosen by config:
- ``clerk_jwks_url`` set  -> verify Clerk-issued RS256 tokens against the JWKS endpoint.
- otherwise (dev/test)    -> verify HS256 tokens signed with ``auth_dev_secret``.

This keeps the app fully runnable/testable without a Clerk account (mint a dev token), while
the production path verifies real Clerk tokens. The token ``sub`` is the user id that scopes
all per-user data.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from core.config import Settings, get_settings


class AuthError(Exception):
    """Raised when a token is missing/invalid (mapped to HTTP 401 at the edge)."""


def mint_dev_token(user_id: str, settings: Settings | None = None) -> str:
    """Mint a local HS256 token for dev/test (and local curl)."""
    settings = settings or get_settings()
    return jwt.encode({"sub": user_id}, settings.auth_dev_secret, algorithm="HS256")


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        if settings.clerk_jwks_url:
            signing_key = _jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
            return dict(
                jwt.decode(
                    token, signing_key.key, algorithms=["RS256"], options={"verify_aud": False}
                )
            )
        return dict(jwt.decode(token, settings.auth_dev_secret, algorithms=["HS256"]))
    except jwt.PyJWTError as exc:
        raise AuthError("invalid token") from exc


def user_id_from_token(token: str, settings: Settings | None = None) -> str:
    claims = decode_token(token, settings)
    subject = claims.get("sub")
    if not subject:
        raise AuthError("token missing 'sub'")
    return str(subject)
