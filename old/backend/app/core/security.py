"""Authentication: provider-agnostic JWT verification (Decision 9).

The IdP is a swappable dependency from day one (the whole point of D9): production verifies
Cognito RS256 tokens via JWKS; dev/test verify HS256 with a shared secret. Swapping to
Keycloak/Ory later means a new verifier behind the same interface — no route changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AuthError, ForbiddenError


@dataclass
class Principal:
    sub: str
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    anonymous: bool = False


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict: ...


class HSVerifier:
    """Dev/test verifier (symmetric secret). Never used in prod."""

    def verify(self, token: str) -> dict:
        import jwt

        try:
            return jwt.decode(
                token,
                settings.jwt_secret or "",
                algorithms=["HS256"],
                audience=settings.jwt_audience,
                options={"verify_aud": settings.jwt_audience is not None},
            )
        except Exception as exc:  # noqa: BLE001
            raise AuthError("Invalid token") from exc


class JWKSVerifier:
    """Production verifier: Cognito RS256 via JWKS (needs cryptography)."""

    def __init__(self, jwks_url: str) -> None:
        import jwt

        self._client = jwt.PyJWKClient(jwks_url)

    def verify(self, token: str) -> dict:
        import jwt

        try:
            key = self._client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={"verify_aud": settings.jwt_audience is not None},
            )
        except Exception as exc:  # noqa: BLE001
            raise AuthError("Invalid token") from exc


def get_verifier() -> TokenVerifier:
    if settings.jwt_algorithm == "HS256":
        return HSVerifier()
    if not settings.cognito_jwks_url:
        raise AuthError("JWKS not configured")
    return JWKSVerifier(settings.cognito_jwks_url)


def _principal_from_claims(claims: dict) -> Principal:
    roles = claims.get("cognito:groups") or claims.get("roles") or []
    return Principal(sub=claims["sub"], email=claims.get("email"), roles=list(roles))


def get_current_user(request: Request) -> Principal:
    """FastAPI dependency: resolve the caller's Principal from the Bearer token."""
    if not settings.auth_enabled:
        return Principal(sub="anonymous", anonymous=True)

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AuthError("Missing bearer token")
    claims = get_verifier().verify(header.removeprefix("Bearer ").strip())
    return _principal_from_claims(claims)


def require_role(role: str):
    def _dep(request: Request) -> Principal:
        principal = get_current_user(request)
        if role not in principal.roles:
            raise ForbiddenError(f"Requires role: {role}")
        return principal

    return _dep
