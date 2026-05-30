/**
 * k6 load test for the Anime Recommender API.
 *
 * Run:
 *   k6 run load_tests/k6_script.js
 *   k6 run --env BASE_URL=http://your-server:8000 load_tests/k6_script.js
 *
 * Stages:
 *   0 → 5 VU  over 30s  (warm-up)
 *   5 → 20 VU over 60s  (ramp)
 *   20 VU     for 60s   (sustained load)
 *   20 → 0 VU over 30s  (cool-down)
 *
 * Thresholds:
 *   - p95 response time < 15s  (LLM streaming is inherently slow)
 *   - error rate < 5%
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("error_rate");
const streamDuration = new Trend("stream_duration_ms");

export const options = {
  stages: [
    { duration: "30s", target: 5 },
    { duration: "60s", target: 20 },
    { duration: "60s", target: 20 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<15000"],
    error_rate: ["rate<0.05"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Obtain a token once at startup (shared across VUs via module scope)
const tokenRes = http.post(
  `${BASE_URL}/v1/auth/token`,
  JSON.stringify({ username: "user", password: "user123" }),
  { headers: { "Content-Type": "application/json" } }
);
const TOKEN = tokenRes.status === 200 ? JSON.parse(tokenRes.body).access_token : "";

if (!TOKEN) {
  console.error("Failed to obtain auth token. Check that the server is running.");
}

const QUERIES = [
  "action anime with a strong female protagonist",
  "dark psychological thriller with moral ambiguity",
  "romance anime set in high school",
  "sci-fi mecha with philosophical themes",
  "slice of life comedy that is calming",
  "historical anime set in feudal Japan",
  "sports anime about volleyball teamwork",
  "fantasy adventure with a detailed magic system",
  "horror anime that is genuinely unsettling",
  "short anime completable in one day",
];

export default function () {
  const query = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const start = Date.now();

  const res = http.post(
    `${BASE_URL}/v1/recommend`,
    JSON.stringify({ query }),
    {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${TOKEN}`,
      },
      timeout: "30s",
    }
  );

  const elapsed = Date.now() - start;
  streamDuration.add(elapsed);

  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "response has SSE data": (r) => r.body.includes("data:"),
    "response contains DONE signal": (r) => r.body.includes("[DONE]"),
    "response time < 15s": (r) => r.timings.duration < 15000,
  });

  errorRate.add(!ok);

  // Respect rate limit: 10 req/min = 1 request per 6 seconds
  sleep(Math.random() * 3 + 6);
}
