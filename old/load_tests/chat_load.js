// k6 load test for the chat endpoint (Decision 23). Validates the Phase-1 NFRs.
// Run: k6 run -e BASE_URL=https://staging.example.com -e TOKEN=<jwt> load_tests/chat_load.js
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const TOKEN = __ENV.TOKEN || "";

export const options = {
  scenarios: {
    // Ramp toward the 300 RPS peak target via concurrent VUs.
    load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: 50 },
        { duration: "3m", target: 200 },
        { duration: "2m", target: 500 }, // peak ~500 concurrent (Phase 1 scale model)
        { duration: "1m", target: 0 },
      ],
    },
  },
  thresholds: {
    // First-token/full-answer NFRs (Phase 1).
    http_req_duration: ["p(95)<2000", "p(99)<4000"],
    http_req_failed: ["rate<0.01"], // 99.9% SLO -> <1% errors
  },
};

const QUESTIONS = [
  "How is the battery backup on these headphones?",
  "Are these good for gaming?",
  "Best earbuds for bass?",
  "Is this product worth the price?",
  "Does it support fast charging?",
];

export default function () {
  const payload = JSON.stringify({ message: QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)] });
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;

  const res = http.post(`${BASE}/chat`, payload, { headers });
  check(res, {
    "status 200": (r) => r.status === 200,
    "has answer": (r) => r.json("answer") !== undefined,
  });
  sleep(1);
}
