# Transformation Plan — P2 Conversational, Rating-aware Product Recommender (Enterprise2)

> **Status:** Phase 3 (plan for approval). No code is written until you sign off on this plan; then Phase 4 executes one step per commit.
> **Source:** `demo/` (Flask + LangChain + AstraDB review-QA). **Output:** repo root. **Decisions:** see [decision-log.md](decision-log.md).
> **Execution constraints this round:** API keys (OpenAI/Groq/Anthropic) **and** a cloud account **are available** — so real embeddings, real LLM calls, RAGAS, real Qdrant, and a real `terraform plan`/cloud deploy are in-scope (not deferred). Local Python target = 3.12.

---

## Sequencing principle — why this order

The methodology says **front-load risk**. The single most fatal uncertainty here is **not** infrastructure — it's *"does a rating-aware hybrid recommender produce good results on 450 reviews / ~30 products?"* If that fails, the project's premise fails, and no amount of EKS fixes it. So **Steps 2–5 build and measure the recommender core first** and end in an explicit **go/no-go gate on the ranking baseline**. Infrastructure uncertainty (EKS/Qdrant ops) comes later because it has a documented fallback (ECS + Qdrant Cloud) and is config-risk, not product-risk.

Every step ends with the system in a **working, runnable state** and adds its own tests. Steps are sized ~½–1 day.

---

## Batch A — Foundation & de-risking the product

### Step 1 — Repo scaffold & tooling
- **Goal:** Empty but correct monorepo skeleton (Decision 22) with quality gates wired.
- **Changes:** `apps/{web,api,ingestion}`, `packages/{core,retrieval,recommender,eval}`, `infra/{terraform,compose}`, `ops/`, `tests/`, `docs/`; `pyproject.toml` (uv, Python 3.12), `ruff`+`mypy`+`pytest` config, `pre-commit` (ruff, gitleaks), `Makefile` (`lint type test eval-ranking eval-rag up`), `.gitignore`, `.env.example`.
- **Tests:** one trivial unit test per package so the suite runs; `make lint type test` green.
- **Verify:** `make lint type test` passes on the empty stubs; tree matches Decision 22.
- **Implements:** D7, D22. **Risk:** Low. **DoD:** clean lint/type/test on scaffold; `.env.example` lists every key.

### Step 2 — Data reframe: review → product aggregation
- **Goal:** Turn 450 review rows into product-level records (the recommender's unit), not raw review chunks.
- **Changes:** `packages/core/models.py` (Pydantic `Review`, `Product`, `Citation`); `apps/ingestion/aggregate.py` (group by `product_id` → `avg_rating`, `review_count`, representative review text, title); a **data-quality report** written to `docs/data-report.md` (product count, rating distribution, review-volume distribution).
- **Tests:** unit tests on aggregation (rating mean, volume count, dedup, empty/edge cases).
- **Verify:** run the aggregator on the CSV → inspect `docs/data-report.md`; confirm product count + rating spread look sane.
- **Implements:** D3 (data foundation). **Risk:** **Medium** (representation quality). **DoD:** CSV → validated `Product[]`; report committed; tests green.

### Step 3 — Qdrant + embeddings + hybrid retrieval
- **Goal:** Index products in Qdrant and retrieve by hybrid (dense + sparse).
- **Changes:** `infra/compose/docker-compose.yml` (Qdrant service); `packages/retrieval/` (OpenAI `text-embedding-3-small`@1536 via `langchain-openai`; `QdrantVectorStore`; dense+sparse named vectors; hybrid query; `VectorStore` interface for reversibility).
- **Tests:** integration test against **real Qdrant in Docker** with **real embeddings** (keys available) — sample queries return topically-correct products.
- **Verify:** `docker compose up qdrant`, run the index script, run the retrieval test; eyeball top-k for 5 sample queries.
- **Implements:** D2, D5, D3. **Risk:** **High** (new tech + real embeddings). **DoD:** hybrid retrieval returns sensible products; embeddings versioned in the collection.

### Step 4 — Recommender ranking core
- **Goal:** The rating-aware ranking blend that *is* the recommender.
- **Changes:** `packages/recommender/ranking.py` — `score = f(semantic_similarity, avg_rating, review_volume_confidence)` with configurable weights; tie-breaking; "min-quality threshold" for the no-match path.
- **Tests:** unit tests — a low-rated but semantically-close product must not outrank a high-rated relevant one; weight-sensitivity tests.
- **Verify:** feed Step-3 retrieval output through ranking; inspect ordering vs naive dense order.
- **Implements:** D3. **Risk:** **High** (product core). **DoD:** deterministic, tested scorer producing a ranked shortlist.

### Step 5 — Ranking eval harness + BASELINE  ⟵ **go/no-go gate**
- **Goal:** Prove (with numbers) the recommender works before we build production scaffolding around it.
- **Changes:** `packages/eval/ranking/` — curated **~50-query golden set** (`query → relevant/irrelevant product_ids`), `Recall@5`, `NDCG@5`, `MRR`, a runner (`make eval-ranking`); baseline written to `docs/eval-baseline.md`.
- **Tests:** metric-correctness unit tests on known fixtures (perfect ranking = 1.0, worst = 0).
- **Verify:** `make eval-ranking` prints metrics; **we review the baseline together and decide go/no-go** (and whether to tune weights, add reranker, or improve aggregation before continuing).
- **Implements:** D19 (ranking). **Risk:** **High** (validates the premise). **DoD:** metrics computed on real data; baseline recorded; **explicit gate passed.**

---

## Batch B — Inference pipeline & API

### Step 6 — LangChain RAG chain + multi-provider fallback
- **Goal:** Grounded explanation for the ranked products, with provider resilience.
- **Changes:** `packages/core/chain.py` — `create_history_aware_retriever` + LCEL chain; grounded-explanation prompt (versioned in `packages/core/prompts/`); **structured output** for the rec list (`with_structured_output`); provider chain Groq→OpenAI→Anthropic via `with_fallbacks`.
- **Tests:** unit (mocked LLM) for chain wiring + structured-output validation; integration with **real Groq**.
- **Verify:** run the chain on a query → grounded explanation + citations to real reviews.
- **Implements:** D4, D6. **Risk:** Medium. **DoD:** chain returns validated rec list + cited explanation; fallback path unit-tested.

### Step 7 — RAGAS eval + baseline
- **Goal:** Answer-quality measurement + a calibrated CI gate threshold.
- **Changes:** `packages/eval/ragas/` — answer-quality golden set; faithfulness / answer-relevancy / context-precision; judge = Claude Sonnet (off-family); `make eval-rag`; baseline + chosen thresholds appended to `docs/eval-baseline.md`.
- **Tests:** harness smoke test on a tiny fixture.
- **Verify:** `make eval-rag` prints RAGAS scores; thresholds set **from the measured baseline** (not blind).
- **Implements:** D19 (RAG). **Risk:** Medium. **DoD:** RAGAS baseline recorded; gate thresholds calibrated.

### Step 8 — FastAPI app + DynamoDB chat history
- **Goal:** The serving API with persistent, **per-user-isolated** conversation (fixes the demo's shared-session bug).
- **Changes:** `infra/compose` add **DynamoDB-local**; `apps/api/` — `/health`, `/metrics`, `/recommend` (sync, ranking-only, p95<300ms target), `/chat` (SSE streaming); Pydantic request/response schemas; `DynamoDBChatMessageHistory` keyed by `user_id:session_id`; single-table access patterns documented in `docs/dynamo-access-patterns.md`.
- **Tests:** integration — SSE streams tokens; **two users get isolated histories** (explicit regression test for the demo bug); history persists across restart.
- **Verify:** `make up` + curl the SSE endpoint; run two sessions; confirm isolation.
- **Implements:** D1, D7, D8 (API), D9 (scoping). **Risk:** Medium. **DoD:** API runs; SSE works; isolation + persistence proven by test.

### Step 9 — 4-layer caching
- **Goal:** Hit the ≥60% cache target that makes the cost NFR achievable.
- **Changes:** `packages/core/cache/` — L0 in-proc LRU (catalog meta), L1 Redis embedding cache, **L2 semantic cache as a Qdrant collection**, L3 Redis response cache; `catalog_version` tag invalidation; singleflight coalescing. Redis added to compose.
- **Tests:** semantic-cache hits a near-duplicate query; version-bump invalidates; singleflight prevents stampede (concurrent-request test).
- **Verify:** replay the golden queries twice → measure per-layer hit rate; record in `docs/eval-baseline.md`.
- **Implements:** D10. **Risk:** Medium. **DoD:** measured hit-rate reported; invalidation + coalescing tested.

---

## Batch C — Production cross-cutting concerns

### Step 10 — Auth (Clerk) + rate limiting + quotas
- **Changes:** Clerk JWT verification middleware (JWKS); every route authed except `/health`; user id scopes all DynamoDB partitions; Redis token-bucket rate limit + daily quotas; 429 + `Retry-After`.
- **Tests:** unauth → 401; over-limit → 429; user A cannot read user B's history.
- **Verify:** hit the API with/without a minted JWT; trip the limit.
- **Implements:** D9, D20. **Risk:** Medium (Clerk new). **DoD:** auth + limits + isolation enforced and tested.

### Step 11 — Observability (OTel + Langfuse)
- **Changes:** OTel SDK in `api`/`worker` → OTLP collector (compose) → Grafana/Tempo/Prometheus (local); Langfuse self-hosted in compose; LangChain `CallbackHandler` → Langfuse; per-request token/cost/latency-per-stage; `ops/grafana/` dashboards-as-code; trace-ID correlation app↔LLM.
- **Tests:** a query emits a Langfuse trace containing cost+tokens+latency; metrics endpoint exposes the real counters (replacing the demo's broken one).
- **Verify:** run a query → open Langfuse → see the trace; open Grafana → see request metrics.
- **Implements:** D13. **Risk:** Medium. **DoD:** end-to-end trace with cost/latency; dashboards render.

### Step 12 — Security + cost controls + kill switch
- **Changes:** system prompt hardening (treat reviews as untrusted) + structured-output validation + **adversarial test fixtures**; Presidio PII scrubber in the log pipeline; kill switch (config/GrowthBook flag `llm_enabled` → 503 degraded + cache still served); per-request cost caps (`max_tokens`, `k`); model routing/escalation (<10% target).
- **Tests:** prompt-injection fixtures don't exfiltrate/trigger; PII redacted in emitted logs; kill switch returns degraded UX; cost caps enforced.
- **Verify:** run the adversarial suite; flip the kill switch; inspect a scrubbed log line.
- **Implements:** D18, D20. **Risk:** Medium. **DoD:** adversarial + PII + kill-switch + caps all tested.

### Step 13 — Failure-mode degradation
- **Changes:** circuit breakers — LLM fallback chain, **Qdrant down/slow → popularity-only ranking** (from DynamoDB catalog cache), Redis pass-through + bulkhead, DynamoDB backoff; "no good match" state (F6).
- **Tests:** chaos unit tests simulate each dependency failing → assert the **named** fallback from Decision 21.
- **Verify:** kill each dependency in compose → observe the degraded-but-up behavior.
- **Implements:** D21. **Risk:** Medium. **DoD:** every Decision-21 row has a passing chaos test.

---

## Batch D — Frontend

### Step 14 — Next.js frontend
- **Changes:** `apps/web/` — chat UI; **recommendation cards stream first, explanation streams below**; citation chips with click-through; `AbortController` cancel; optimistic user message; Clerk auth UI; "no good match" + degraded-mode banner states.
- **Tests:** component tests (render, cancel); Playwright e2e of the full local flow.
- **Verify:** `make up` + open the web app; confirm cards appear before the explanation; cancel mid-stream.
- **Implements:** D8. **Risk:** Medium. **DoD:** e2e local flow green; cards-first behavior verified.

---

## Batch E — Containerization & local orchestration

### Step 15 — Dockerize all services + compose parity
- **Changes:** multi-stage, non-root, distroless-where-feasible Dockerfiles for `api`/`web`/`worker`; full `docker-compose` stack (api, web, worker, qdrant, redis, dynamodb-local, langfuse, otel-collector).
- **Tests:** `docker compose config` validates; container smoke test hits `/health`.
- **Verify:** `docker compose up` runs the whole stack end-to-end on your machine.
- **Implements:** D15 (containers). **Risk:** Medium. **DoD:** whole stack runs in compose; images are non-root + slim.

### Step 16 — Helm charts + local-k8s validate
- **Changes:** `ops/helm/` charts; Qdrant **StatefulSet** + PVC; `api` Deployment+HPA; `worker` Deployment + **KEDA** ScaledObject; Langfuse; Services/Ingress; PodDisruptionBudgets.
- **Tests:** `helm template` renders; `kubeconform`/`kubectl --dry-run` validates manifests.
- **Verify:** render charts; **if `kind`/`minikube` is available, deploy locally**; otherwise validation-only here and real deploy happens in Phase 6 (cloud).
- **Implements:** D15 (orchestration). **Risk:** Medium-High (ops). **DoD:** charts render + validate; local deploy if tooling present, else flagged for Phase 6.

---

## Batch F — Cloud IaC & CI/CD (ready-to-deploy; actual rollout is Phase 6)

### Step 17 — Terraform modules + plan
- **Changes:** `infra/terraform/` modules — `vpc, eks, dynamodb, qdrant, redis (ElastiCache), s3, cloudfront, waf, observability`; ESO + IRSA wiring; region-templated.
- **Tests:** `terraform validate` + `tflint`; `terraform plan` against the **real account** (no apply — Phase 6).
- **Verify:** review the `plan` output together for surprises/cost.
- **Implements:** D14, D15, D17, D23. **Risk:** **High** (real cloud). **DoD:** validate + clean `plan`; cost estimate noted.

### Step 18 — CI/CD pipeline + eval gate
- **Changes:** `.github/workflows/` — `ci.yml` (lint/type/unit/integration-with-compose/build/Trivy/push-ECR via OIDC), `eval-gate.yml` (ranking + RAGAS, **blocks on regression vs `main`**), `cd.yml` (tf plan/apply hook + ArgoCD sync); `ops/argocd/` + Argo Rollouts canary manifests.
- **Tests:** CI green on a PR; **intentionally regress a prompt → eval gate must fail** (proves the gate works).
- **Verify:** open a PR; watch CI; push a regression to confirm the block.
- **Implements:** D16. **Risk:** Medium. **DoD:** CI green; eval gate demonstrably blocks a regression.

---

## After the plan steps

- **Phase 5 — Hardening pass:** Package-1 hardening checklist (secrets/dependency/license audit, Trivy, k6 load test, chaos drill, backup/restore drill, runbook, alerting, cost alarms, log retention, RTBF path).
- **Phase 6 — Deployment sequence:** local Docker → local k8s → `terraform plan` → **dev (apply+smoke)** → **staging (load test at production-like volume)** → **prod (gated promote, canary, rollback ready, dashboards live)**. Real cloud this round.
- **Phase 7 — Portfolio writeup:** problem, architecture diagram, key decisions/trade-offs, **real** scale/latency/cost numbers from the load test + Langfuse, "what I'd do differently."

## Risk register (front-loaded items first)

| Step | Risk | Why | Mitigation / fallback |
|---|---|---|---|
| 5 | Ranking baseline too low | Tiny dataset may not support good recs | Go/no-go gate; tune weights, add reranker, improve aggregation, or re-scope |
| 3 | Qdrant hybrid + real embeddings | New tech, real keys | Interface-isolated; pgvector/Qdrant-Cloud fallback |
| 17 | Terraform against real cloud | Cost + first real apply | Plan-only here; apply gated in Phase 6; cost review |
| 16 | EKS/Qdrant StatefulSet ops | Highest ops surface | Documented fallback: ECS Fargate + Qdrant Cloud (Decision 15 trigger) |
| 8 | DynamoDB single-table modeling | Access patterns lock early | Patterns documented up front in Step 8; reviewed before build |
```
