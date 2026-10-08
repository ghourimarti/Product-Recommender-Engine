"""Create or update the app Secret on kind from a filtered .env (todos 6.5.6, 6.6.1).

Only allow-listed keys are copied. Compose-only settings (host URLs and ports, Langfuse, the
build-time NEXT_PUBLIC_* values) never reach the cluster: the chart sets in-cluster URLs itself.

Two auth profiles, because the browser and the load tests need different tokens:
  clerk    APP_ENV=dev + CLERK_JWKS_URL. The API accepts only Clerk RS256 session tokens.
  devauth  APP_ENV=local, no CLERK_JWKS_URL. The API accepts HS256 tokens signed with
           AUTH_DEV_SECRET (ops/load/mint_tokens.py), for k6 drills that outlast Clerk's
           ~60 s session tokens.
AUTH_DEV_BYPASS is forced to false in both, so a request without a token is always a 401.

Values go to kubectl on stdin and are never printed; only key names are. Pods read the Secret
once, at start, so an existing api Deployment is restarted to pick up the new profile (web
reads only CLERK_SECRET_KEY, which no profile changes).

    uv run python infra/kind/kind_secret.py --profile clerk
    uv run python infra/kind/kind_secret.py --profile devauth --dry-run   # key names only
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

SECRET_NAME = "p2-secrets"
PROFILE_ANNOTATION = "p2.dev/auth-profile"
FIELD_MANAGER = "kind-secret"

# Copied from .env when set. Every other .env key is left out.
SHARED_KEYS: tuple[str, ...] = (
    # LLM tiers and embeddings
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_MODEL",
    "GROQ_MODEL",
    "GROQ_MAX_OUTPUT_TOKENS",
    "ANTHROPIC_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    # Data stores. Their URLs and endpoints come from the chart, not from here.
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "DYNAMODB_TABLE",
    "AWS_REGION",
    # Live shopping source
    "SERPAPI_API_KEY",
    # Clerk's server-side key for the web middleware (the web pod reads only this key)
    "CLERK_SECRET_KEY",
    # Behaviour and cost controls
    "RATE_LIMIT_PER_MINUTE",
    "RATE_LIMIT_PER_DAY",
    "LLM_ENABLED",
    "MAX_OUTPUT_TOKENS",
    "LOG_LEVEL",
)

# Without these nothing works: embeddings for the seed and every query, and the web pod's
# secretKeyRef (a missing key stops the pod from starting).
REQUIRED_KEYS: tuple[str, ...] = ("OPENAI_API_KEY", "CLERK_SECRET_KEY")


@dataclass(frozen=True)
class Profile:
    app_env: str
    keys: tuple[str, ...]  # profile-only keys: copied from .env, and required


PROFILES: dict[str, Profile] = {
    "clerk": Profile(app_env="dev", keys=("CLERK_JWKS_URL",)),
    "devauth": Profile(app_env="local", keys=("AUTH_DEV_SECRET",)),
}


def profile_settings(profile: str) -> dict[str, str]:
    """The non-secret values a profile sets, overriding anything in .env."""
    return {"APP_ENV": PROFILES[profile].app_env, "AUTH_DEV_BYPASS": "false"}


def build_secret_data(env: Mapping[str, str | None], profile: str) -> dict[str, str]:
    """The Secret's keys and values for one auth profile. Raises ValueError naming missing keys."""
    data: dict[str, str] = {}
    for key in SHARED_KEYS + PROFILES[profile].keys:
        value = env.get(key)
        if value:
            data[key] = value
    missing = [key for key in REQUIRED_KEYS + PROFILES[profile].keys if key not in data]
    if missing:
        raise ValueError(f"missing or empty in .env: {', '.join(missing)}")
    return data | profile_settings(profile)


def secret_manifest(data: Mapping[str, str], profile: str, namespace: str) -> dict[str, Any]:
    """The Secret, with base64 `data` rather than `stringData` (see apply_secret)."""
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {
            "name": SECRET_NAME,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/part-of": "p2-recommender",
                "app.kubernetes.io/managed-by": FIELD_MANAGER,
            },
            "annotations": {PROFILE_ANNOTATION: profile},
        },
        "data": {key: base64.b64encode(data[key].encode()).decode() for key in sorted(data)},
    }


def apply_secret(manifest: Mapping[str, Any], context: str) -> int:
    """Server-side apply through stdin; returns kubectl's exit code.

    Server-side, because a client-side `kubectl apply` copies every value into the
    last-applied-configuration annotation, which `kubectl describe` prints. Base64 `data`,
    because server-side apply tracks who owns each `data` key, so a key that a profile switch
    drops (CLERK_JWKS_URL or AUTH_DEV_SECRET) is removed from the Secret instead of lingering.
    """
    command = ["kubectl", "--context", context, "apply", "--server-side"]
    command += [f"--field-manager={FIELD_MANAGER}", "--force-conflicts", "-f", "-"]
    return subprocess.run(command, input=json.dumps(manifest), text=True, check=False).returncode


def restart_api(context: str, namespace: str) -> int:
    """Roll the api Deployment, if it exists, and wait; returns kubectl's exit code."""
    kubectl = ["kubectl", "--context", context, "-n", namespace]
    found = subprocess.run(
        [*kubectl, "get", "deployment", "api", "--ignore-not-found", "-o", "name"],
        capture_output=True,
        text=True,
        check=False,
    )
    if found.returncode:
        return found.returncode  # kubectl has already printed why
    if not found.stdout.strip():
        print("  no api Deployment yet, so nothing to restart")
        return 0
    print("  restarting the api so it loads the new profile")
    for step in (["rollout", "restart"], ["rollout", "status", "--timeout=300s"]):
        code = subprocess.run([*kubectl, *step, "deployment/api"], check=False).returncode
        if code:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--namespace", default="p2")
    parser.add_argument("--context", default="kind-p2")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--dry-run", action="store_true", help="print key names; apply nothing")
    args = parser.parse_args(argv)

    if not args.context.startswith("kind-"):
        parser.error(f"refusing context {args.context!r}: this script is for kind clusters only")
    if not args.env_file.is_file():
        parser.error(f"{args.env_file} not found")
    env = dotenv_values(args.env_file)
    try:
        data = build_secret_data(env, args.profile)
    except ValueError as exc:
        parser.error(str(exc))

    forced = profile_settings(args.profile)
    copied = sorted(set(data) - set(forced))
    left_out = sorted(set(env) - set(copied))
    print(f"{SECRET_NAME}: profile {args.profile}, namespace {args.namespace}, {args.context}")
    print(f"  from .env ({len(copied)}): {' '.join(copied)}")
    print(f"  set by the profile: {' '.join(f'{k}={v}' for k, v in forced.items())}")
    print(f"  left out ({len(left_out)}): {' '.join(left_out)}")
    if args.dry_run:
        return 0
    code = apply_secret(secret_manifest(data, args.profile, args.namespace), args.context)
    return code or restart_api(args.context, args.namespace)


if __name__ == "__main__":
    raise SystemExit(main())
