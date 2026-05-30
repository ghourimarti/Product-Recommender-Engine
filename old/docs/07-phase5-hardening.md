# Phase 5 — Production Hardening Pass

Status of each checklist item. **Done** = implemented + verified here. **Partial** = mechanism in place, full proof needs a deployed env (Phase 6). **Deferred** = needs cloud/real traffic, with reason.

| # | Item | Status | Evidence / Action |
|---|---|---|---|
| 1 | **Secrets audit** | ✅ Done | Repo scan clean (no AWS/Groq/OpenAI keys, no private keys); no `.env` tracked; prod via Secrets Manager + External Secrets Operator (D17) |
| 2 | **Dependency audit** | ◑ Partial | `pip-audit -r requirements.txt` runs in CI (non-blocking on transitive); `npm audit` deferred (needs `npm install` — runs in frontend CI job) |
| 3 | **License audit** | ✅ Done | Only weak-copyleft (MPL-2.0: `certifi`, `orjson`) among deps — fine to use unmodified; no GPL/AGPL strong-copyleft |
| 4 | **Security scan (SAST + image)** | ✅ Done | `bandit -r app` clean (0 issues; 2 reviewed `# nosec`: container bind, retry jitter); Trivy image scan in CD fails on HIGH/CRITICAL |
| 5 | **Load test** | ◑ Partial | k6 scripts + NFR thresholds ready (`load_tests/`); real run vs staging is Phase 6 (produces the p50/p95/p99 + cost numbers) |
| 6 | **Chaos test** | ◑ Partial | Degradation unit-tested (retry/breaker/cache-down/engine-down, Step 16); container-kill drill (kill LLM/Qdrant/Redis) scripted in Phase 6 against the live stack |
| 7 | **Backup & restore drill** | ⊘ Deferred | RDS automated snapshots provisioned (Terraform); a real restore drill needs the cloud DB — Phase 6. Procedure in `runbook.md` |
| 8 | **Incident runbook** | ✅ Done | `docs/runbook.md` (symptom→cause→action table, kill switch, re-index, RTBF) |
| 9 | **On-call alerting** | ✅ Done | Prometheus rules (`infra/monitoring/alerts.yml`): BackendDown, HighErrorRate (SLO), p99 latency; Alertmanager→PagerDuty/Slack wired at deploy |
| 10 | **Cost-alert thresholds** | ✅ Done | Prometheus `HighLLMSpendPerHour` (>$5/h); AWS Budgets at 80% of $2,500/mo ceiling (Terraform) |
| 11 | **Log retention policy** | ✅ Done | CloudWatch log group retention 14d (non-prod) / 90d (prod); logs PII-scrubbed at the formatter (D18) |
| 12 | **Data-deletion / RTBF** | ✅ Done | `delete_user_data` (cascade) + admin `DELETE /admin/users/{id}` (RBAC) + test; cache entries expire via TTL |

## Items requiring the live environment (Phase 6)
- Real load-test numbers, chaos drills against running containers, RDS restore drill, and Alertmanager paging require a deployed cluster + cloud DB. These are executed in the deployment sequence, not faked here.

## Verified this pass
- bandit 0 issues; secrets scan clean; RTBF deletion test green; full suite **54 passed**.
