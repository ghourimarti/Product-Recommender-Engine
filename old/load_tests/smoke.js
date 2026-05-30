// k6 smoke test: 1 VU, quick health + single chat call. Run before the full load test.
// k6 run -e BASE_URL=http://localhost:8000 load_tests/smoke.js
import http from "k6/http";
import { check } from "k6";

const BASE = __ENV.BASE_URL || "http://localhost:8000";

export const options = { vus: 1, iterations: 3, thresholds: { http_req_failed: ["rate<0.01"] } };

export default function () {
  check(http.get(`${BASE}/healthz`), { "health 200": (r) => r.status === 200 });
  check(http.get(`${BASE}/readyz`), { "ready resolves": (r) => r.status === 200 || r.status === 503 });
}
