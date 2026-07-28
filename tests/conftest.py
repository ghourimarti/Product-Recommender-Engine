"""Shared test helpers.

Service reachability is derived from **settings/env**, never from hardcoded ports. Two
integration test files previously probed ``6333``/``6379`` — the container defaults — but the
stack moved to the 2000-range (Qdrant 2001, Redis 2004). The probes therefore always failed and
those tests *silently skipped*, so the 4-layer cache, the kill-switch and the API endpoints were
covered by zero executing tests while the suite still reported "89 passed". Deriving the port
from the same setting the app uses makes that class of false confidence impossible.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse


def url_reachable(url: str, default_port: int) -> bool:
    """True if host:port parsed from ``url`` accepts a TCP connection."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def qdrant_reachable() -> bool:
    from core.config import get_settings

    return url_reachable(get_settings().qdrant_url, default_port=2001)


def redis_reachable() -> bool:
    from core.config import get_settings

    return url_reachable(get_settings().redis_url, default_port=2004)


def dynamodb_reachable() -> bool:
    from core.config import get_settings

    return url_reachable(get_settings().dynamodb_endpoint, default_port=2003)
