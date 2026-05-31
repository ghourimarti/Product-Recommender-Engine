// k6 load test for the /recommend path (Decision 10/12 scaling targets).
// Run:  API_URL=http://localhost:8080 TOKEN=<dev jwt> k6 run ops/load/k6-recommend.js
//
// Target NFRs (docs/decision-log.md): ranking-only p95 < 300ms; cache hit-rate makes this
// achievable at ~200 RPS. Adjust stages/thresholds to the environment under test.

import http from "k6/http";
import { check, sleep } from "k6";

const API_URL = __ENV.API_URL || "http://localhost:8080";
const TOKEN = __ENV.TOKEN || "";

const QUERIES = [
  "good bass headphones",
  "cheap bluetooth neckband",
  "wireless earbuds with long battery life",
  "wired earphones for music",
  "earbuds for gaming",
];

export const options = {
  stages: [
    { duration: "30s", target: 50 },   // ramp
    { duration: "1m", target: 200 },   // sustain ~200 concurrent
    { duration: "30s", target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<300"],  // ranking-only p95 < 300ms
    http_req_failed: ["rate<0.01"],    // < 1% errors
  },
};

export default function () {
  const query = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.post(
    `${API_URL}/recommend`,
    JSON.stringify({ query, k: 3 }),
    { headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}` } },
  );
  check(res, {
    "status 200": (r) => r.status === 200,
    "has products": (r) => (r.json("products") || []).length > 0,
  });
  sleep(1);
}
