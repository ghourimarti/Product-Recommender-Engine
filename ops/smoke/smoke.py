"""Smoke-test a deployed P2 through its public entry point (todo 6.6.4).

Every request goes through the Gateway, as a browser's would: the web app at /, the API under
/api (the Gateway strips the prefix). In order:

  web        GET  /                    200 HTML
  health     GET  /api/health          200 {"status": "ok"}, so the /api prefix is stripped
  no token   POST /api/recommend       401: the API fails closed
  dev token  POST /api/recommend       devauth: 200 with products · clerk: 401 (RS256 only)
  devauth only:
  chat       POST /api/chat            SSE through the Gateway: recommendations, tokens, done
  history    GET  /api/account/export  the chat turn was stored (DynamoDB); then deleted
  --aggregate only (spends ONE live SerpApi search):
  aggregate  POST /api/aggregate x2    live offers, then the same answer from the Redis cache

The first two checks retry for up to --wait seconds, because a fresh rollout can take a moment
to reach the Gateway (todo 6.3.5). Nothing else retries: a failure there is a real failure.

    uv run python ops/smoke/smoke.py --auth-mode devauth
    uv run python ops/smoke/smoke.py --auth-mode clerk --base-url http://127.0.0.1 \
        --host app.localhost
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import httpx

from core.auth import mint_dev_token

QUERY = "comfortable wireless headphones with good bass"  # on-topic for the 9-product catalog
AGGREGATE_QUERY = "wireless earbuds"


class SmokeFailure(Exception):
    pass


def expect(condition: object, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def parse_sse(lines: Iterable[str]) -> Iterator[tuple[str, dict[str, Any]]]:
    """(event, data) pairs from a text/event-stream body, yielded as they arrive."""
    event, data = "message", list[str]()
    for line in itertools.chain(lines, [""]):  # lazy: a list here would buffer the whole stream
        if not line:
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
        elif line.startswith("event:"):
            event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data.append(line.removeprefix("data:").strip())


def check_web(client: httpx.Client) -> str:
    response = client.get("/")
    expect(response.status_code == 200, f"HTTP {response.status_code}")
    expect("<html" in response.text.lower(), "not an HTML page")
    return f"HTTP 200, {len(response.content):,} bytes of HTML"


def check_health(client: httpx.Client) -> str:
    response = client.get("/api/health")
    expect(response.status_code == 200, f"HTTP {response.status_code}: {response.text[:120]}")
    expect(response.json() == {"status": "ok"}, f"unexpected body {response.text[:120]}")
    return 'HTTP 200 {"status": "ok"}'


def check_no_token(client: httpx.Client) -> str:
    response = client.post("/api/recommend", json={"query": QUERY, "k": 3})
    expect(response.status_code == 401, f"expected 401, got HTTP {response.status_code}")
    return "HTTP 401 without a token"


def check_dev_token(client: httpx.Client, token: str, auth_mode: str) -> str:
    response = client.post("/api/recommend", json={"query": QUERY, "k": 3}, headers=bearer(token))
    if auth_mode == "clerk":
        hint = " (the API accepted it, so it runs the devauth profile)"
        expect(
            response.status_code == 401,
            f"expected 401, got HTTP {response.status_code}"
            + (hint if response.status_code == 200 else ""),
        )
        return "HTTP 401: an HS256 dev token is rejected; only Clerk RS256 tokens pass"
    expect(response.status_code == 200, f"HTTP {response.status_code}: {response.text[:160]}")
    body = response.json()
    expect(body["products"] and not body["no_match"], "no products for an on-topic query")
    return f"HTTP 200, {len(body['products'])} products, top {body['products'][0]['title'][:40]!r}"


def check_chat(client: httpx.Client, token: str, session_id: str) -> str:
    body = {"query": QUERY, "session_id": session_id, "k": 3}
    events: list[tuple[str, dict[str, Any]]] = []
    first_event = 0.0
    start = time.perf_counter()
    with client.stream("POST", "/api/chat", json=body, headers=bearer(token)) as response:
        expect(response.status_code == 200, f"HTTP {response.status_code}")
        content_type = response.headers.get("content-type", "")
        expect(content_type.startswith("text/event-stream"), f"content-type {content_type!r}")
        for event in parse_sse(response.iter_lines()):
            first_event = first_event or time.perf_counter() - start
            events.append(event)
    total = time.perf_counter() - start
    names = [name for name, _ in events]
    expect(names[:1] == ["recommendations"], f"first event {names[:1]}")
    expect(names[-1:] == ["done"], f"last event {names[-1:]}")
    done = events[-1][1]
    expect(not done.get("degraded"), "degraded answer: every LLM provider failed (LLM keys?)")
    expect(not done.get("no_match"), "no_match for an on-topic query")
    chunks = names.count("token")
    expect(chunks > 0, "no token events")
    # First event well before the last = streamed through the Gateway, not buffered.
    timing = f"first at {first_event:.2f}s of {total:.2f}s"
    return f"{len(events)} events, {chunks} token chunks, {timing}"


def check_history(client: httpx.Client, token: str, session_id: str) -> str:
    response = client.get("/api/account/export", headers=bearer(token))
    expect(response.status_code == 200, f"export: HTTP {response.status_code}")
    turn = [m for m in response.json()["user_messages"] if m["session_id"] == session_id]
    expect(sorted(m["role"] for m in turn) == ["ai", "human"], f"stored turn {turn}")
    response = client.delete("/api/account", headers=bearer(token))
    expect(response.status_code == 200, f"delete: HTTP {response.status_code}")
    deleted = response.json()["deleted"]
    expect(deleted == len(turn), f"deleted {deleted} of {len(turn)} items")
    return f"chat turn stored (human + ai) and deleted ({deleted} items)"


def check_aggregate(client: httpx.Client, token: str) -> str:
    body = {"query": AGGREGATE_QUERY, "k": 3}
    start = time.perf_counter()
    first = client.post("/api/aggregate", json=body, headers=bearer(token))
    live = time.perf_counter() - start
    expect(first.status_code == 200, f"HTTP {first.status_code}: {first.text[:160]}")
    result = first.json()
    expect(not result["source_unavailable"], f"source unavailable: {result['detail']}")
    expect(result["offers"], "no offers")
    start = time.perf_counter()
    second = client.post("/api/aggregate", json=body, headers=bearer(token))
    cached = time.perf_counter() - start
    expect(second.status_code == 200, f"repeat: HTTP {second.status_code}")
    expect(second.json() == result, "repeat answer differs, so it didn't come from the cache")
    return f"{len(result['offers'])} live offers in {live:.2f}s; identical repeat in {cached:.2f}s"


def retry(check: Callable[[], str], wait_seconds: float) -> str:
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            return check()
        except (httpx.TransportError, SmokeFailure):
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--auth-mode", choices=["clerk", "devauth"], required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1")
    # Windows resolvers (Python's included) don't map *.localhost to 127.0.0.1, so connect to
    # the IP and route by Host header.
    parser.add_argument("--host", default="app.localhost")
    parser.add_argument("--wait", type=float, default=60, help="retry budget for the first checks")
    parser.add_argument("--aggregate", action="store_true", help="spend one live SerpApi search")
    args = parser.parse_args(argv)

    run_id = uuid.uuid4().hex[:8]
    token = mint_dev_token(f"smoke-{run_id}")  # a fresh user: own rate-limit bucket and history
    session_id = f"smoke-{run_id}"
    checks: list[tuple[str, Callable[[], str]]] = []
    with httpx.Client(base_url=args.base_url, headers={"Host": args.host}, timeout=120) as client:
        checks.append(("web", lambda: retry(lambda: check_web(client), args.wait)))
        checks.append(("health", lambda: retry(lambda: check_health(client), args.wait)))
        checks.append(("no token", lambda: check_no_token(client)))
        checks.append(("dev token", lambda: check_dev_token(client, token, args.auth_mode)))
        if args.auth_mode == "devauth":
            checks.append(("chat", lambda: check_chat(client, token, session_id)))
            checks.append(("history", lambda: check_history(client, token, session_id)))
            if args.aggregate:
                checks.append(("aggregate", lambda: check_aggregate(client, token)))
        print(f"smoke {args.base_url} (Host: {args.host}), auth mode {args.auth_mode}")
        failures = 0
        for name, check in checks:
            start = time.perf_counter()
            try:
                status, detail = "PASS", check()
            except (SmokeFailure, httpx.HTTPError, KeyError, ValueError) as exc:
                status, detail, failures = "FAIL", f"{type(exc).__name__}: {exc}", failures + 1
            print(f"  {status}  {name:<10} {time.perf_counter() - start:6.2f}s  {detail}")
    print(f"{len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
