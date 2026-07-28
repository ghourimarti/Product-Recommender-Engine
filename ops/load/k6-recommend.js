// k6 load test for the /recommend path (scaling targets).
//
// ── Why this script had to change ────────────────────────────────────────────────────────────
// The previous version sent every virtual user's traffic with a SINGLE token. All VUs therefore
// shared one user_id, hit the 30-requests/minute per-user rate limit within seconds, and the run
// measured nothing but 429s. It could not validate any throughput target.
//
// It also reused 5 queries, so after warm-up every request was an L3 cache HIT — the run measured
// the cache, not the system. Both are fixed below:
//   * TOKENS  — a comma-separated list; each VU picks its own, so the limiter is not the bottleneck.
//   * MODE    — "cached" (repeat queries) or "cold" (unique query per iteration).
//
// ── Usage ────────────────────────────────────────────────────────────────────────────────────
//   # mint one token per VU (dev-auth mode) — see `make load-tokens`
//   TOKENS=$(uv run python -m ops.load.mint_tokens 50)
//
//   # cache-hit throughput (the fast path)
//   API_URL=http://localhost:2011 TOKENS=$TOKENS MODE=cached k6 run ops/load/k6-recommend.js
//
//   # cold path (every query unique -> retrieval + ranking on every request)
//   API_URL=http://localhost:2011 TOKENS=$TOKENS MODE=cold   k6 run ops/load/k6-recommend.js
//
// NOTE: do NOT point this at /aggregate. Every distinct query there spends a METERED SerpApi
// search (free plan = 250/month); a load test would destroy the quota in seconds.

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const API_URL = __ENV.API_URL || "http://localhost:2011";
const MODE = __ENV.MODE || "cached"; // "cached" | "cold"

// One token per VU keeps the per-user rate limiter out of the measurement.
const TOKENS = (__ENV.TOKENS || __ENV.TOKEN || "").split(",").filter(Boolean);

const QUERIES = [
  "good bass headphones",
  "cheap bluetooth neckband",
  "wireless earbuds with long battery life",
  "wired earphones for music",
  "earbuds for gaming",
];

const rateLimited = new Rate("rate_limited_429");

export const options = {
  stages: [
    { duration: "20s", target: 25 },
    { duration: "40s", target: 50 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    // Cold path does real retrieval + ranking, so it is held to the end-to-end NFR (p95 < 2s);
    // the cached path is held to the ranking-only NFR (p95 < 300ms).
    http_req_duration: [MODE === "cold" ? "p(95)<2000" : "p(95)<300"],
    http_req_failed: ["rate<0.01"],
    rate_limited_429: ["rate<0.01"], // if this trips, you passed too few TOKENS
  },
};

export function setup() {
  if (TOKENS.length === 0) {
    throw new Error("No TOKENS provided. Run: TOKENS=$(uv run python -m ops.load.mint_tokens 50)");
  }
  return { tokenCount: TOKENS.length };
}

export default function () {
  const token = TOKENS[__VU % TOKENS.length]; // each VU = its own user -> no shared rate limit
  const query =
    MODE === "cold"
      ? `${QUERIES[__ITER % QUERIES.length]} variant ${__VU}-${__ITER}` // unique -> cache miss
      : QUERIES[Math.floor(Math.random() * QUERIES.length)];

  const res = http.post(`${API_URL}/recommend`, JSON.stringify({ query, k: 3 }), {
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  });

  rateLimited.add(res.status === 429);
  check(res, {
    "status 200": (r) => r.status === 200,
    "not rate limited": (r) => r.status !== 429,
    // A cold/off-topic query may legitimately return no_match, so only assert the shape.
    "well-formed body": (r) => r.json("products") !== undefined,
  });
  sleep(0.5);
}
