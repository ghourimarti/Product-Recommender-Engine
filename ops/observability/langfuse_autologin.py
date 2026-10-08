"""Langfuse's front door on http://localhost:2008: every page opens already signed in.

Langfuse has no anonymous mode, so this sits in front of it and does the real login for you.
Every request is passed through to the in-network Langfuse unchanged, except a browser opening a
page (a navigation) without a valid session: then it signs in server-side (NextAuth credentials
flow: CSRF token, then the bootstrapped admin's email and password) and redirects the browser
back to the same page with the session cookie. That also covers a session that went stale
(`make upv` wipes Langfuse's users), an expired one, and "Sign out", which lands on the sign-in
page and is signed straight back in.

API calls (/api/*: the SDKs' Basic-auth ingestion, the UI's own tRPC) and static assets are never
touched. Local-only by design: the port is published on 127.0.0.1. Standard library only, so it
runs on a stock python:alpine image with nothing installed.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

UPSTREAM_HOST = os.environ.get("LANGFUSE_INTERNAL_HOST", "langfuse-web")
UPSTREAM_PORT = int(os.environ.get("LANGFUSE_INTERNAL_PORT", "3000"))
PUBLIC_URL = os.environ.get("LANGFUSE_PUBLIC_URL", "http://localhost:2008").rstrip("/")
PROJECT_ID = os.environ.get("LANGFUSE_INIT_PROJECT_ID", "")
EMAIL = os.environ.get("LANGFUSE_INIT_USER_EMAIL", "")
PASSWORD = os.environ.get("LANGFUSE_INIT_USER_PASSWORD", "")
SESSION_COOKIE = "next-auth.session-token"
SIGN_IN_PAGES = ("/auth/sign-in", "/auth/sign-up", "/auth/error")
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
ASSET = re.compile(r"\.(js|css|map|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|txt|json|webmanifest)$")


class LoginError(Exception):
    pass


def landing_path() -> str:
    return f"/project/{PROJECT_ID}/traces" if PROJECT_ID else "/"


def cookie_pairs(set_cookie_headers: list[str]) -> dict[str, str]:
    """name -> value from Set-Cookie headers (attributes dropped)."""
    pairs: dict[str, str] = {}
    for header in set_cookie_headers:
        name, _, rest = header.partition("=")
        pairs[name.strip()] = rest.split(";", 1)[0]
    return pairs


def request_cookies(cookie_header: str) -> dict[str, str]:
    """name -> value from a request's Cookie header."""
    pairs: dict[str, str] = {}
    for part in cookie_header.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep:
            pairs[name] = value
    return pairs


def browser_cookies(
    set_cookie_headers: list[str], old: Mapping[str, str] | None = None
) -> list[str]:
    """The session cookie(s) to hand the browser, re-issued as plain host-only cookies.

    NextAuth may split a large session into .0/.1 chunks, so every session-token* cookie goes,
    and any chunk the browser still holds from an older session is expired.
    """
    fresh = {
        k: v for k, v in cookie_pairs(set_cookie_headers).items() if k.startswith(SESSION_COOKIE)
    }
    out = [f"{k}={v}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000" for k, v in fresh.items()]
    for name in old or {}:
        if name.startswith(SESSION_COOKIE) and name not in fresh:
            out.append(f"{name}=; Path=/; Max-Age=0")
    return out


def is_navigation(method: str, path: str, headers: Mapping[str, str]) -> bool:
    """A browser opening a page, as opposed to an API call or an asset."""
    if method not in ("GET", "HEAD"):
        return False
    route = urlsplit(path).path
    if route.startswith(("/api/", "/_next/")) or ASSET.search(route):
        return False
    mode = headers.get("Sec-Fetch-Mode", "")
    return mode == "navigate" or (not mode and "text/html" in headers.get("Accept", ""))


def after_sign_in(path: str) -> str:
    """Where to send the browser once signed in: back where it was going, never off-site."""
    parts = urlsplit(path)
    if parts.path.startswith(SIGN_IN_PAGES):
        target = parse_qs(parts.query).get("callbackUrl", [""])[0]
        if target.startswith(PUBLIC_URL):
            target = target[len(PUBLIC_URL) :] or "/"
        if (
            not target.startswith("/")
            or target.startswith("//")
            or target.startswith(SIGN_IN_PAGES)
        ):
            target = landing_path()
        return target
    return landing_path() if parts.path in ("", "/") else path


def upstream() -> http.client.HTTPConnection:
    return http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=120)


def session_valid(cookie_header: str) -> bool:
    """Does Langfuse accept this browser's session? (False after `make upv` wiped its users.)"""
    if SESSION_COOKIE not in cookie_header:
        return False
    conn = upstream()
    try:
        conn.request("GET", "/api/auth/session", headers={"Cookie": cookie_header})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status == 200 and bool(json.loads(body or b"{}").get("user"))
    except (OSError, ValueError):
        return True  # Langfuse unreachable: let the request through and show its real error
    finally:
        conn.close()


def sign_in() -> list[str]:
    """Run the NextAuth credentials flow against the in-network Langfuse; return Set-Cookies."""
    if not (EMAIL and PASSWORD):
        raise LoginError("LANGFUSE_INIT_USER_EMAIL / LANGFUSE_INIT_USER_PASSWORD are not set")
    conn = upstream()
    try:
        conn.request("GET", "/api/auth/csrf")
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            raise LoginError(f"Langfuse /api/auth/csrf answered HTTP {resp.status}")
        csrf = json.loads(body)["csrfToken"]
        jar = cookie_pairs(resp.headers.get_all("Set-Cookie") or [])
        form = urlencode(
            {
                "csrfToken": csrf,
                "email": EMAIL,
                "password": PASSWORD,
                "callbackUrl": PUBLIC_URL + landing_path(),
                "json": "true",
            }
        )
        conn.request(
            "POST",
            "/api/auth/callback/credentials",
            body=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items()),
            },
        )
        resp = conn.getresponse()
        resp.read()
        cookies = resp.headers.get_all("Set-Cookie") or []
        if not any(c.startswith(SESSION_COOKIE) for c in cookies):
            raise LoginError(
                f"Langfuse rejected the login (HTTP {resp.status}, no session cookie): "
                "check LANGFUSE_INIT_USER_EMAIL / _PASSWORD match the bootstrapped user"
            )
        return cookies
    except (OSError, ValueError, KeyError) as exc:
        raise LoginError(f"Langfuse is not reachable yet ({type(exc).__name__})") from exc
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0: each response closes its connection, so a body of unknown length can be streamed.
    protocol_version = "HTTP/1.0"

    def handle_any(self) -> None:
        if self.path.startswith("/healthz"):
            self._page(200, "ok", "text/plain")
            return
        headers = {k: v for k, v in self.headers.items()}
        if is_navigation(self.command, self.path, headers):
            cookie_header = self.headers.get("Cookie", "")
            signing_page = urlsplit(self.path).path.startswith(SIGN_IN_PAGES)
            if signing_page or not session_valid(cookie_header):
                self._sign_in_and_redirect(request_cookies(cookie_header))
                return
        self._proxy()

    def _sign_in_and_redirect(self, old: dict[str, str]) -> None:
        try:
            cookies = browser_cookies(sign_in(), old)
        except LoginError as exc:
            self._page(
                503,
                "<meta http-equiv='refresh' content='10'><h2>Langfuse is not ready</h2>"
                f"<p>{exc}. Retrying every 10 s; Langfuse's first start takes 1-3 min.</p>",
            )
            return
        sys.stderr.write(f"langfuse front door: signed in for {self.path.split('?')[0]}\n")
        self.send_response(302)
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Location", after_sign_in(self.path))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        conn = upstream()
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            self.send_response(resp.status, resp.reason)
            for name, value in resp.getheaders():
                if name.lower() not in HOP_BY_HOP:
                    self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                while chunk := resp.read1(65536):  # as it arrives: streamed responses stay live
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except OSError:
            self._page(502, "<meta http-equiv='refresh' content='10'><h2>Langfuse is starting</h2>")
        finally:
            conn.close()

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = handle_any

    def _page(self, code: int, body: str, ctype: str = "text/html") -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # a line per asset would drown the logs; sign-ins are logged where they happen


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"langfuse front door on :{port} -> {UPSTREAM_HOST}:{UPSTREAM_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()  # noqa: S104 - in a container
