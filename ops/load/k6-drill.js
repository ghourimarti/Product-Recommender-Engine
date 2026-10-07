// k6 load for the production-behaviour drills (todo 6.7): steady traffic while something breaks.
//
// Unlike k6-recommend.js (throughput), this holds a CONSTANT arrival rate for the whole drill and
// fails on any non-200: during a rollout, a pod deletion or a node loss, "zero errors" is the bar.
// Requests rotate through TOKENS by iteration, so each user stays far under the per-user limit
// (30/min): with RATE r/s and N tokens a user sends 60*r/N per minute, so pass N > 2*r.
//
//   TOKENS=$(uv run python -m ops.load.mint_tokens 60) \
//   API_URL=http://app.localhost/api RESOLVE=app.localhost=127.0.0.1 \
//   RATE=10 DURATION=3m k6 run ops/load/k6-drill.js
//
// RESOLVE pins hostnames to IPs inside k6 (Windows' resolver doesn't map *.localhost to loopback).
// MODE=cold makes every query unique, so requests miss the Redis cache and reach Qdrant (and pay
// for one OpenAI embedding each): use it when the drill breaks something behind the cache. Set RUN
// to something new per run, or a re-run repeats (and hits the cache for) earlier queries.

import http from "k6/http";
import exec from "k6/execution";
import { check } from "k6";
import { Counter } from "k6/metrics";

const API_URL = __ENV.API_URL || "http://app.localhost/api";
const TOKENS = (__ENV.TOKENS || "").split(",").filter(Boolean);
const RATE = Number(__ENV.RATE || 10);
const DURATION = __ENV.DURATION || "3m";
const RESOLVE = (__ENV.RESOLVE || "").split(",").filter(Boolean);
const COLD = __ENV.MODE === "cold";
// Part of every cold query, so a re-run doesn't repeat (and hit the cache for) an earlier run's queries.
const RUN = __ENV.RUN || "run";

const QUERIES = [
  "good bass headphones",
  "cheap bluetooth neckband",
  "wireless earbuds with long battery life",
];

const non200 = new Counter("non_200"); // tagged with the status, so the summary shows what failed

export const options = {
  hosts: Object.fromEntries(RESOLVE.map((pair) => pair.split("="))),
  scenarios: {
    drill: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.max(10, RATE * 2),
      maxVUs: RATE * 10, // headroom when a request is slow, so the arrival rate holds
    },
  },
  thresholds: {
    http_req_failed: ["rate==0"],
    non_200: ["count==0"],
  },
};

export function setup() {
  if (TOKENS.length <= 2 * RATE) {
    throw new Error(`pass more than ${2 * RATE} TOKENS for RATE=${RATE}, or users hit the limit`);
  }
}

export default function () {
  // The test-wide iteration number: __ITER counts per VU, so VUs would share a token at once.
  const i = exec.scenario.iterationInTest;
  const token = TOKENS[i % TOKENS.length];
  const base = QUERIES[i % QUERIES.length];
  const query = COLD ? `${base} ${RUN}-${i}` : base; // a unique query misses every cache layer
  const res = http.post(`${API_URL}/recommend`, JSON.stringify({ query, k: 3 }), {
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    timeout: "10s",
  });
  if (res.status !== 200) {
    non200.add(1, { status: String(res.status) });
  }
  check(res, { "status 200": (r) => r.status === 200 });
}
