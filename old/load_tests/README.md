# Load testing (Decision 23)

Validates the Phase-1 NFRs: first-token p95 ≤ 2s / p99 ≤ 4s, 300 RPS peak, <1% errors (99.9% SLO).

## Run (against staging, never prod first)
```bash
k6 run -e BASE_URL=http://localhost:8000 load_tests/smoke.js
k6 run -e BASE_URL=https://staging.example.com -e TOKEN=<jwt> load_tests/chat_load.js
```

## Tuning checklist — where this breaks first under load, and the fix (from the build-spec)
1. **Vector search latency** → Qdrant replicas; tune HNSW `ef`; push metadata filters down.
2. **Embedding service throughput** → scale `embedding` replicas (HPA on CPU); batch.
3. **LLM provider rate limits / cost** → semantic cache (biggest lever), model tiering,
   multiple keys/regions.
4. **Postgres connections** → add PgBouncer; raise pool size; read replica for history reads.
5. **Backend CPU** → HPA `maxReplicas`; uvicorn `--workers`; ensure async (no sync blocking).
6. **Cold starts on scale-up** → min replicas / warm pool; readiness gating (already wired).

## What to record for the portfolio writeup (Phase 7)
- p50/p95/p99 at sustained 100 RPS and at 300 RPS peak
- cache hit-rate and resulting cost/request (from /metrics: llm_cost_usd_total)
- the breaking point (RPS where p95 exceeds 2s) and which component saturated
