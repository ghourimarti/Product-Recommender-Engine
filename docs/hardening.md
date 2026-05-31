# Production Hardening Checklist (Phase 5)

Status against the Package-1 hardening checklist + the methodology's Phase-5 categories.
**Done** = implemented & verified here · **Partial** = implemented, full verification needs
cloud/tooling · **Deferred** = needs Phase 6 (real cluster/cloud) or external tooling.

| Item | Status | Evidence / notes |
|---|---|---|
| Secrets audit | **Done** | No secrets in repo; `.env` gitignored; secrets via Secrets Manager + ESO (Decision 17); gitleaks in pre-commit. |
| Dependency vulnerability audit | **Done** | `pip-audit` → **no known vulnerabilities**; wired into CI (`ci.yml`). |
| License audit | **Done** | `pip-licenses`: all permissive (MIT/BSD/Apache; MPL-2.0 file-level). No GPL/AGPL strong-copyleft. 2 UNKNOWN + 1 "proprietary" are metadata gaps, not blockers. |
| Code security scan | **Done** | `bandit -r packages apps` → **0 issues** (the 2 best-effort try/except in observability converted to `contextlib.suppress`). |
| Container image scan | **Partial** | Trivy step added to CI (`image-scan` job, fails on HIGH/CRITICAL). Not run locally (trivy not installed). |
| Eval gate (regression) | **Done** | Ranking gate (NDCG@3/MRR vs `baseline.json`) + RAGAS-style answer-quality baseline; CI-blocking. |
| Prompt-injection / output safety | **Done** | Structural (LLM writes only reasons; product set fixed by ranking) + prompt hardening + adversarial test. |
| PII handling | **Done** | `redact_pii` on logged queries; tests for email/phone/card. |
| Right-to-be-forgotten + DSAR | **Done** | `DELETE /account` (one-partition delete) + `GET /account/export`; `DELETE /history`; store + endpoint tests. |
| Rate limiting / quotas / kill-switch | **Done** | 30/min + 500/day per user (429 + Retry-After); `LLM_ENABLED` kill-switch; cost caps (`max_output_tokens`). |
| Failure-mode degradation / chaos | **Done** | Circuit breaker + popularity fallback + resilient cache; 6 chaos unit tests (Qdrant/Redis/LLM down). |
| Incident runbook | **Done** | `docs/runbook.md` (playbooks, kill-switch, restore drill, GDPR, escalation). |
| Alerting thresholds | **Partial** | `ops/observability/alerts.yaml` (5xx, p95, cache-hit, cost/hr). Wiring to Alertmanager/PagerDuty = deploy step. |
| Cost-alert thresholds | **Partial** | Defined (`LLMCostPerHourHigh`); Langfuse cost export + CloudWatch alarm wired in Phase 6. |
| Log retention policy | **Done (documented)** | 30-day logs; chat-history TTL; PII redacted at emission (runbook + Decision 24). |
| Load test | **Partial** | `ops/load/k6-recommend.js` (p95<300ms, <1% err at ~200 RPS). Run on staging in Phase 6 (k6 not installed locally). |
| Backup & restore drill | **Deferred** | Procedure in runbook; DynamoDB PITR + Qdrant snapshots in IaC. Live drill = Phase 6 (staging). |
| Image slimming | **Deferred (with reason)** | API image ~725MB; **fastembed/onnxruntime is on the serving path** (sparse half of hybrid retrieval), so it can't simply be dropped. Future option: a separate sparse-embedding service or a server-side sparse model. |
| On-call alerting setup | **Deferred** | Needs a real Alertmanager/PagerDuty integration (Phase 6). |

## Summary
Everything verifiable without a live cloud/cluster is **Done**: clean dependency + code +
license audits, RTBF/DSAR, runbook, eval gates, CI scans (pip-audit + bandit run in CI; Trivy job
added). The **Deferred/Partial** items are exactly the ones gated on a real cluster/cloud or
absent local tooling (Trivy run, k6 load test, restore drill, Alertmanager) — these belong to
**Phase 6 (deploy)**. Image slimming is deferred with a concrete reason (sparse-embedding dep).
