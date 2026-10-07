"""The kind Secret builder: what reaches the cluster from .env, per auth profile."""

from __future__ import annotations

import base64
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from core.config import Settings
from infra.kind.kind_secret import (
    PROFILES,
    REQUIRED_KEYS,
    SHARED_KEYS,
    build_secret_data,
    main,
    restart_api,
    secret_manifest,
)

# Shaped like the real .env: app settings plus compose-only keys that must stay out.
ENV: dict[str, str | None] = {
    "OPENAI_API_KEY": "sk-openai-test",
    "GROQ_API_KEY": "gsk-test",
    "SERPAPI_API_KEY": "",  # empty: left out, the aggregator degrades instead
    "CLERK_SECRET_KEY": "sk_test_clerk",
    "CLERK_JWKS_URL": "https://example.clerk.accounts.dev/.well-known/jwks.json",
    "AUTH_DEV_SECRET": "hs256-dev-secret-0123456789abcdef0123",
    "QDRANT_API_KEY": "qdrant-test",
    "APP_ENV": "local",
    "QDRANT_URL": "http://localhost:2001",
    "REDIS_URL": "redis://localhost:2004/0",
    "DYNAMODB_ENDPOINT": "http://localhost:2003",
    "API_PORT": "2011",
    "CORS_ORIGINS": "http://localhost:2012",
    "LANGFUSE_SECRET_KEY": "lf-test",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test_clerk",
    "AWS_ACCESS_KEY_ID": None,
}


def test_clerk_profile_verifies_clerk_tokens_only() -> None:
    data = build_secret_data(ENV, "clerk")
    assert data["APP_ENV"] == "dev"
    assert data["CLERK_JWKS_URL"] == ENV["CLERK_JWKS_URL"]
    assert "AUTH_DEV_SECRET" not in data  # the HS256 signing key has no business here


def test_devauth_profile_verifies_minted_tokens_only() -> None:
    data = build_secret_data(ENV, "devauth")
    assert data["APP_ENV"] == "local"
    assert data["AUTH_DEV_SECRET"] == ENV["AUTH_DEV_SECRET"]
    # With a JWKS URL present the API would switch to RS256 and reject every minted token.
    assert "CLERK_JWKS_URL" not in data


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_anonymous_bypass_is_off_in_every_profile(profile: str) -> None:
    assert build_secret_data(ENV, profile)["AUTH_DEV_BYPASS"] == "false"


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_compose_only_and_empty_keys_stay_out(profile: str) -> None:
    data = build_secret_data(ENV, profile)
    for key in (
        "QDRANT_URL",  # the chart sets in-cluster URLs; a compose URL would break them
        "REDIS_URL",
        "DYNAMODB_ENDPOINT",
        "API_PORT",
        "CORS_ORIGINS",
        "LANGFUSE_SECRET_KEY",
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",  # build-time only
        "SERPAPI_API_KEY",  # empty in .env
        "AWS_ACCESS_KEY_ID",  # unset in .env
    ):
        assert key not in data, key
    assert data["CLERK_SECRET_KEY"] == ENV["CLERK_SECRET_KEY"]  # the web pod needs it in both


@pytest.mark.parametrize(
    ("profile", "removed"),
    [("clerk", "CLERK_JWKS_URL"), ("devauth", "AUTH_DEV_SECRET"), ("clerk", "OPENAI_API_KEY")],
)
def test_missing_required_key_fails_without_echoing_values(profile: str, removed: str) -> None:
    env = {k: v for k, v in ENV.items() if k != removed}
    with pytest.raises(ValueError, match=removed) as excinfo:
        build_secret_data(env, profile)
    assert not any(v and v in str(excinfo.value) for v in env.values())


def test_every_key_maps_to_a_setting() -> None:
    # Catches a typo in the allow-list, which would otherwise drop a setting silently.
    allowed = set(SHARED_KEYS) | {k for p in PROFILES.values() for k in p.keys}
    allowed |= {"APP_ENV", "AUTH_DEV_BYPASS"}
    web_only = {"CLERK_SECRET_KEY"}
    assert set(REQUIRED_KEYS) <= allowed
    for key in allowed - web_only:
        assert key.lower() in Settings.model_fields, key


def test_manifest_is_base64_data_annotated_with_the_profile() -> None:
    data = build_secret_data(ENV, "devauth")
    manifest = secret_manifest(data, "devauth", "p2")
    assert manifest["metadata"]["name"] == "p2-secrets"
    assert manifest["metadata"]["namespace"] == "p2"
    assert manifest["metadata"]["annotations"] == {"p2.dev/auth-profile": "devauth"}
    assert "stringData" not in manifest
    decoded = {k: base64.b64decode(v).decode() for k, v in manifest["data"].items()}
    assert decoded == data


def test_refuses_a_non_kind_context(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=x\nCLERK_SECRET_KEY=y\nCLERK_JWKS_URL=z\n")
    with pytest.raises(SystemExit) as excinfo:
        main(["--profile", "clerk", "--context", "do-fra1-prod", "--env-file", str(env_file)])
    assert excinfo.value.code == 2


def _fake_kubectl(
    found: str, calls: list[list[str]]
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=found if "get" in command else "")

    return run


@pytest.mark.parametrize(
    ("found", "steps"),
    [
        ("", []),  # first install: the Secret comes before the chart, nothing to restart
        (
            "deployment.apps/api\n",
            [["rollout", "restart"], ["rollout", "status", "--timeout=300s"]],
        ),
    ],
)
def test_restart_rolls_the_api_only_if_it_exists(
    monkeypatch: pytest.MonkeyPatch, found: str, steps: list[list[str]]
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_kubectl(found, calls))
    assert restart_api("kind-p2", "p2") == 0
    # Each call is: kubectl --context kind-p2 -n p2 <step...> deployment/api
    assert [call[5:-1] for call in calls[1:]] == steps


def test_dry_run_prints_names_never_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in ENV.items() if v))
    assert main(["--profile", "devauth", "--env-file", str(env_file), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY" in out and "APP_ENV=local" in out
    for key, value in ENV.items():
        if value and key != "APP_ENV":
            assert value not in out, f"value of {key} printed"
