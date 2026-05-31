# Runbook — P2 Product Recommender

Operational playbook for on-call. The system degrades rather than fails (Decision 21), so most
incidents are "quality/latency degraded," not "down."

## Dashboards & signals
- **Grafana** (app): request rate, p50/p95/p99 latency by route, 5xx rate, `cache_hits_total` /
  `cache_misses_total` by layer.
- **Langfuse** (LLM): per-request tokens / cost / latency, escalation rate, online eval scores.
- **Jaeger** (traces): `recommend.pipeline` span + per-request spans (trace id links to Langfuse).
- Key metrics: `http_request_duration_seconds` (p95 SLO < 2s), `http_requests_total{status}`,
  `cache_hits_total` (target hit-rate ≥ 60%).

## Incident playbooks (failure → user-visible behavior → action)

| Symptom | What's happening | First action |
|---|---|---|
| 5xx spike on `/chat` | LLM providers failing | Check Langfuse error rate; provider chain auto-falls Groq→OpenAI→Anthropic; if all down, `/chat` already serves a static template. Verify provider status pages. |
| p95 latency > 2s | Qdrant slow or cache cold | Check cache hit-rate; if Qdrant p95 high, the breaker trips to **popularity-only** ranking. Scale Qdrant replicas / check node pressure. |
| "Showing top matches; explanations unavailable" banner | All LLMs down OR `LLM_ENABLED=false` | Confirm whether kill-switch was flipped intentionally; else check provider keys/quota. |
| Cost spike alert | Runaway usage / low cache hit | Inspect Langfuse cost-per-hour + per-user; if abuse, tighten rate limits; **kill-switch**: set `LLM_ENABLED=false` (serves cached recs, no LLM spend). |
| 429s from a user | Rate limit hit (30/min, 500/day) | Expected for abuse; raise limits per-tenant only with justification. |
| Recommendations look generic | Retrieval circuit open (popularity fallback) | Check Qdrant health + embeddings provider; once healthy, the breaker half-opens automatically. |

## Kill-switch
Set `LLM_ENABLED=false` (env / config) and restart the API (or flip the flag at runtime once
GrowthBook is wired). `/recommend` and the recommendation cards still work; only LLM explanations
are skipped. Re-enable by setting `LLM_ENABLED=true`.

## Backup & restore drill (run quarterly in staging)
- **DynamoDB:** PITR enabled (35-day window) + on-demand backups (Terraform). Restore:
  `aws dynamodb restore-table-to-point-in-time --source-table-name <t> --target-table-name <t>-restore --use-latest-restorable-time`, repoint `DYNAMODB_TABLE`, smoke-test history read/write.
- **Qdrant:** scheduled snapshots to S3. Restore: create collection, `PUT /collections/<c>/snapshots/recover` from the S3 snapshot URL, then re-run `retrieval.index` only if the snapshot is stale.
- **Drill acceptance:** restored history round-trips for a test user; retrieval returns expected products on the golden queries.

## Chaos drill (verify degradation; covered by `tests/unit/test_resilience.py`)
Locally: `docker compose stop qdrant` → `/recommend` returns popularity-only (no error);
`docker compose stop redis` → still serves (cache bypassed, rate-limit fails open);
unset provider keys → `/chat` streams the static template.

## GDPR / data lifecycle (Decision 24)
- **Right-to-be-forgotten:** `DELETE /account` (authenticated) → deletes all of the user's data in
  one DynamoDB partition. Also exposed via `DynamoChatHistory.delete_user`.
- **DSAR export:** `GET /account/export` returns the user's stored messages.
- **Session clear:** `DELETE /history?session_id=...`.
- **Retention:** chat history TTL (DynamoDB `ttl` attribute); logs retained 30 days; PII redacted
  from logs at emission (`core.security.redact_pii`).

## Escalation
1. Acknowledge alert (PagerDuty/Slack). 2. Identify failing dependency from the table above.
3. Apply first action; if customer-impacting > 15 min, flip kill-switch to stop spend/errors while
   investigating. 4. Write a short postmortem (trigger, impact, fix, follow-up).
