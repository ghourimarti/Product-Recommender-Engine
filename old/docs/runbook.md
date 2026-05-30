# Operational Runbook

## Local
```bash
docker compose up --build
docker compose run --rm backend alembic upgrade head     # migrate
docker compose run --rm backend python -m scripts.ingest # load corpus (needs keys)
# UI http://localhost:3000 · API http://localhost:8000 · Grafana http://localhost:3001
```

## Deploy / promote (CD)
- Push to `main` → CI (lint/tests/RAGAS gate) → CD builds images by git SHA → deploys dev →
  **manual approval** → staging (same digest).
- Production promotion: re-run with the prod environment gate (Phase 6).

## Rollback
```bash
helm rollback rec            # previous release
helm history rec             # see revisions
```
Trigger: failed smoke test, error-rate alert, or p99 SLO burn after deploy.

## Kill switch (cost / incident load-shed)
Set `KILL_SWITCH=true` (env/ConfigMap) and restart backend → new chat work is shed (503) and
any LLM calls forced to the cheap tier. Use when spend alerts fire or a provider melts down.

## Common incidents
| Symptom | Likely cause | Action |
|---|---|---|
| 503 on /readyz | RAG build failed (keys / Qdrant / embedding down) | check logs `rag_build_failed`; verify Qdrant + embedding `/healthz`; secrets present |
| High latency p99 | LLM provider slow / cold scale-up | confirm fallback firing; raise HPA min; check cache hit-rate |
| 429s spiking | rate limit / budget hit | inspect per-user; raise limits if legitimate; check for abuse |
| Empty/"no info" answers | retrieval miss / re-index gap | check Qdrant collection count; re-run ingest; bump `CATALOG_VERSION` |
| Cost alert | cache cold / tier escalation | verify semantic cache; review escalation rate; consider kill switch |
| Redis down | cache unavailable | service degrades automatically (bypasses cache); restore ElastiCache |

## Data
- **Re-index without downtime:** ingest into a new collection, then flip `VECTOR_COLLECTION_NAME` + bump `CATALOG_VERSION` (invalidates cache).
- **Backup/restore:** RDS automated snapshots; restore drill is a Phase-5 hardening item.
- **Right-to-be-forgotten (GDPR):** delete the user's rows (users/conversations/messages cascade) + their cached entries expire via TTL.

## Observability
- Metrics: `/metrics` (Prometheus) → Grafana dashboards.
- LLM traces/cost: Langfuse.
- Alert on: SLO burn (error rate, p99), cost/hour, cache hit-rate drop, readiness flapping.
