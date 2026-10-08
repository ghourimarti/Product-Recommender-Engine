"""Wait until a URL answers 2xx, then say so. Never fails the build: it reports and exits 0.

    uv run python -m ops.stack.wait_http "http://127.0.0.1:{API_PORT}/health" --name API

{KEY} placeholders are filled from .env, so make needs no shell to read a port.
"""

from __future__ import annotations

import argparse
import time

import httpx

from ops.stack.catalog import load_env


def wait(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=3).is_success:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--name", default="service")
    args = parser.parse_args(argv)
    args.url = args.url.format_map(load_env())
    print(f"  waiting for the {args.name} ({args.url}, up to {args.timeout:.0f}s)...", flush=True)
    started = time.monotonic()
    if wait(args.url, args.timeout):
        print(f"  {args.name} healthy after {time.monotonic() - started:.0f}s")
    else:
        print(f"  {args.name} NOT healthy after {args.timeout:.0f}s: docker logs p2-api --tail 50")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
