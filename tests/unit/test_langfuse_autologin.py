"""Langfuse's front door: pages open signed in; API calls and assets pass through untouched."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from ops.observability import langfuse_autologin as door

PAGE = "/project/p2-recommender-project/traces"
BROWSER = {"Accept": "text/html", "Sec-Fetch-Mode": "navigate"}


class FakeLangfuse(BaseHTTPRequestHandler):
    """Just enough NextAuth: csrf, credentials callback, session; plus a page and an API."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/auth/csrf":
            self._json({"csrfToken": "t"}, cookies=["next-auth.csrf-token=c; Path=/"])
        elif self.path == "/api/auth/session":
            valid = "next-auth.session-token=good" in self.headers.get("Cookie", "")
            self._json({"user": {"email": "a@b"}} if valid else {})
        elif self.path.startswith("/api/public/health"):
            self._json({"status": "OK", "auth": self.headers.get("Authorization", "")})
        else:
            self._json({"page": self.path})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode()
        if self.path == "/api/auth/callback/credentials" and "password=pw" in body:
            self._json({}, cookies=["next-auth.session-token=good; Path=/; HttpOnly"])
        else:
            self._json({"echo": body})

    def _json(self, data: object, cookies: list[str] | None = None) -> None:
        raw = json.dumps(data).encode()
        self.send_response(200)
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


@pytest.fixture
def front(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    upstream, up_port = _serve(FakeLangfuse)
    monkeypatch.setattr(door, "UPSTREAM_HOST", "127.0.0.1")
    monkeypatch.setattr(door, "UPSTREAM_PORT", up_port)
    monkeypatch.setattr(door, "PROJECT_ID", "p2-recommender-project")
    monkeypatch.setattr(door, "EMAIL", "a@b")
    monkeypatch.setattr(door, "PASSWORD", "pw")
    proxy, port = _serve(door.Handler)
    yield f"http://127.0.0.1:{port}"
    proxy.shutdown()
    upstream.shutdown()


def test_a_page_without_a_session_comes_back_signed_in(front: str) -> None:
    r = httpx.get(front + PAGE, headers=BROWSER)
    assert r.status_code == 302 and r.headers["location"] == PAGE
    assert r.headers["set-cookie"].startswith("next-auth.session-token=good")


def test_a_stale_session_is_replaced(front: str) -> None:
    r = httpx.get(front + PAGE, headers={**BROWSER, "Cookie": "next-auth.session-token=stale"})
    assert r.status_code == 302 and "next-auth.session-token=good" in r.headers["set-cookie"]


def test_a_valid_session_passes_straight_through(front: str) -> None:
    r = httpx.get(front + PAGE, headers={**BROWSER, "Cookie": "next-auth.session-token=good"})
    assert r.status_code == 200 and r.json() == {"page": PAGE}


def test_the_sign_in_page_signs_in_and_returns_to_the_callback(front: str) -> None:
    r = httpx.get(front + "/auth/sign-in?callbackUrl=%2Fproject%2Fx%2Fsessions", headers=BROWSER)
    assert r.status_code == 302 and r.headers["location"] == "/project/x/sessions"


def test_api_calls_are_proxied_untouched(front: str) -> None:
    r = httpx.get(front + "/api/public/health", auth=("pk", "sk"))
    assert r.status_code == 200 and r.json()["auth"].startswith("Basic ")
    posted = httpx.post(front + "/api/trpc/x", content=b'{"a":1}')
    assert posted.json() == {"echo": '{"a":1}'}


@pytest.mark.parametrize(
    ("method", "path", "headers", "expected"),
    [
        ("GET", PAGE, BROWSER, True),
        ("GET", PAGE, {"Accept": "text/html"}, True),  # older browsers: no Sec-Fetch-Mode
        ("GET", "/api/public/traces", BROWSER, False),
        ("GET", "/_next/static/chunks/main.js", {"Sec-Fetch-Mode": "no-cors"}, False),
        ("GET", "/favicon.ico", BROWSER, False),
        ("POST", PAGE, BROWSER, False),
        ("GET", PAGE, {"Sec-Fetch-Mode": "cors", "Accept": "text/html"}, False),
    ],
)
def test_is_navigation(method: str, path: str, headers: dict[str, str], expected: bool) -> None:
    assert door.is_navigation(method, path, headers) is expected


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/", f"/project/{door.PROJECT_ID}/traces" if door.PROJECT_ID else "/"),
        ("/project/x/sessions?a=1", "/project/x/sessions?a=1"),
        ("/auth/sign-in?callbackUrl=http%3A%2F%2Flocalhost%3A2008%2Fproject%2Fy", "/project/y"),
        ("/auth/sign-in?callbackUrl=https%3A%2F%2Fevil.example", door.landing_path()),
        ("/auth/sign-in?callbackUrl=%2F%2Fevil.example", door.landing_path()),
        ("/auth/sign-in", door.landing_path()),
    ],
)
def test_after_sign_in_never_leaves_the_site(path: str, target: str) -> None:
    assert door.after_sign_in(path) == target


def test_stale_cookie_chunks_are_expired() -> None:
    fresh = ["next-auth.session-token=new; Path=/; HttpOnly"]
    old = {"next-auth.session-token.0": "a", "next-auth.session-token.1": "b", "other": "x"}
    cookies = door.browser_cookies(fresh, old)
    assert cookies[0].startswith("next-auth.session-token=new;")
    assert "next-auth.session-token.0=; Path=/; Max-Age=0" in cookies
    assert not any(c.startswith("other") for c in cookies)
