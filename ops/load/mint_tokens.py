"""Mint N dev JWTs (one per k6 virtual user) so the per-user rate limiter isn't the bottleneck.

The load test previously drove every virtual user through ONE token — i.e. one user_id — so it
tripped the 30/min per-user limit immediately and measured nothing but 429s.

    TOKENS=$(uv run python -m ops.load.mint_tokens 50)
    API_URL=http://localhost:2011 TOKENS=$TOKENS k6 run ops/load/k6-recommend.js
"""

from __future__ import annotations

import sys

from core.auth import mint_dev_token


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    print(",".join(mint_dev_token(f"loadtest-{i}") for i in range(count)))


if __name__ == "__main__":
    main()
