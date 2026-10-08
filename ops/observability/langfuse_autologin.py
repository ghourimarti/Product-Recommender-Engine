"""Open Langfuse already signed in: http://localhost:2019 -> logged in, on the project's traces.

Langfuse has no anonymous mode, so this does the REAL login for you. It signs in to the
in-network Langfuse (NextAuth credentials flow: fetch a CSRF token, post the bootstrap admin's
email and password) and hands the browser the session cookie with a redirect to the UI.
Cookies are scoped by host, not port, so a cookie set by localhost:2019 is sent to
localhost:2008 too. The session then lasts 30 days; after `make downv` just open the link again.

Local-only by design: the port is published on 127.0.0.1. Standard library only, so it runs on
a stock python:alpine image with nothing installed.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode

UPSTREAM_HOST = os.environ.get("LANGFUSE_INTERNAL_HOST", "langfuse-web")
UPSTREAM_PORT = int(os.environ.get("LANGFUSE_INTERNAL_PORT", "3000"))
PUBLIC_URL = os.environ.get("LANGFUSE_PUBLIC_URL", "http://localhost:2008").rstrip("/")
PROJECT_ID = os.environ.get("LANGFUSE_INIT_PROJECT_ID", "")
EMAIL = os.environ.get("LANGFUSE_INIT_USER_EMAIL", "")
PASSWORD = os.environ.get("LANGFUSE_INIT_USER_PASSWORD", "")
SESSION_COOKIE = "next-auth.session-token"


class LoginError(Exception):
    pass


def landing_url() -> str:
    return f"{PUBLIC_URL}/project/{PROJECT_ID}/traces" if PROJECT_ID else f"{PUBLIC_URL}/"


def cookie_pairs(set_cookie_headers: list[str]) -> dict[str, str]:
    """name -> value from Set-Cookie headers (attributes dropped)."""
    pairs: dict[str, str] = {}
    for header in set_cookie_headers:
        name, _, rest = header.partition("=")
        pairs[name.strip()] = rest.split(";", 1)[0]
    return pairs


def browser_cookies(set_cookie_headers: list[str]) -> list[str]:
    """The session cookie(s) to hand the browser, re-issued as plain host-only cookies.

    NextAuth may split a large session into .0/.1 chunks, so every session-token* cookie goes.
    No Domain attribute: host-only for "localhost", which every localhost port then shares.
    """
    out = []
    for name, value in cookie_pairs(set_cookie_headers).items():
        if name.startswith(SESSION_COOKIE):
            out.append(f"{name}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000")
    return out


def sign_in() -> list[str]:
    """Run the NextAuth credentials flow against the in-network Langfuse; return Set-Cookies."""
    if not (EMAIL and PASSWORD):
        raise LoginError("LANGFUSE_INIT_USER_EMAIL / LANGFUSE_INIT_USER_PASSWORD are not set")
    conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=15)
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
                "callbackUrl": landing_url(),
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
        cookies = browser_cookies(resp.headers.get_all("Set-Cookie") or [])
        if not cookies:
            raise LoginError(
                f"Langfuse rejected the login (HTTP {resp.status}, no session cookie): "
                "check LANGFUSE_INIT_USER_EMAIL / _PASSWORD match the bootstrapped user"
            )
        return cookies
    except (OSError, ValueError, KeyError) as exc:
        raise LoginError(
            f"Langfuse is not reachable yet ({type(exc).__name__}); retry in a minute"
        ) from exc
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server's naming
        if self.path.startswith("/healthz"):
            self._send(200, "ok")
            return
        try:
            cookies = sign_in()
        except LoginError as exc:
            page = (
                "<h2>Langfuse auto-login failed</h2>"
                f"<p>{exc}</p><p>Or sign in yourself at <a href='{PUBLIC_URL}'>{PUBLIC_URL}</a>"
                " (credentials: <code>make service_ls</code>).</p>"
            )
            self._send(503, page, "text/html")
            return
        self.send_response(302)
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Location", landing_url())
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _send(self, code: int, body: str, ctype: str = "text/plain") -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        if not self.path.startswith("/healthz"):
            sys.stderr.write("autologin: " + fmt % args + "\n")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"langfuse-autologin on :{port} -> {landing_url()}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()  # noqa: S104 - in a container
