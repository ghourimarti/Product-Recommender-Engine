# Phase 3 — Transformation Plan

> Status: **DRAFT / awaiting sign-off.** Takes the demo (Flask + AstraDB + LCEL + Groq + in-memory history) → the locked target architecture (Decision Log 05). **Risk front-loaded:** the genuinely *uncertain* changes (Qdrant migration, retrieval quality, core rewrite) come early while flexibility is high; the *laborious-but-predictable* infra comes later. Every step ends with a runnable system (docker-compose locally through Step 19; cluster from Step 20). No step leaves the repo broken.

**Source/target:** transform in place into `P2-Product-Recommendion-engine-Enterprise/`, using `...-Demo/` as the starting point and `extras/P1-Enterprise/` as a layout reference (not to copy blindly).

Legend: **[R]** = high-risk/high-uncertainty step.

| # | Step | What changes | Tests added | Verify | Definition of Done |
|---|---|---|---|---|---|
| 1 | **Repo scaffold + config hygiene** | Create monorepo dirs; move `flipkart/` → `backend/app/`; `pydantic-settings` config; `.env.example`; remove hardcoded values; pin deps | smoke import test | run app in new layout | Demo runs unchanged from new structure; no secrets in code |
| 2 | **Flask → FastAPI** (parity) | Replace Flask with FastAPI; port the single chat endpoint; add `/healthz` `/readyz`; structured logging + exceptions wired | unit: health; integration: chat parity | `curl /chat` matches old `/get` | FastAPI serves same answers; health endpoints live |
| 3 | **Abstract RAG core** | Introduce `Retriever`/`Generator`/`VectorStore` interfaces; wrap current LCEL+AstraDB as adapters | unit: interface contracts | app works through abstraction | App runs via interfaces; AstraDB still backing |
| 4 | **[R] AstraDB → Qdrant** | Qdrant adapter + ingestion; Qdrant in docker-compose; migrate the 450-row corpus | integration: ingest+retrieve on Qdrant | parity check vs AstraDB results | Retrieval works on Qdrant; AstraDB removed |
| 5 | **[R] Eval harness (baseline first)** | Golden Q/A set + RAGAS runner (offline); record baseline scores | eval: RAGAS runs | `make eval` prints scores | Baseline faithfulness/relevancy/context scores recorded |
| 6 | **[R] Advanced retrieval** | Hybrid (dense+sparse) + reranker behind feature flags; history-aware rewrite kept | eval: scores vs baseline | RAGAS improves vs Step 5 | Measurable retrieval-quality gain; flags allow bypass |
| 7 | **Postgres data layer** | RDS-ready schema (users, conversations, messages, feedback, audit); SQLAlchemy + Alembic | unit: models; integration: CRUD | migrations apply; rows persist | Schema + migrations run on local Postgres |
| 8 | **Fix per-user/session history** | Replace shared `"user-session"` dict; persist history keyed by per-client session token | integration: two sessions isolated | two browsers ≠ shared history | The shared-memory bug is gone; history persists |
| 9 | **Streaming SSE API + citations** | Token streaming endpoint; cancel (abort) + retry; response schema with citations | integration: stream + cancel | tokens stream; cancel stops | SSE streaming + citations + cancel/retry work |
| 10 | **Self-hosted embedding service** | Extract bge-base into its own container; backend calls it; ingestion uses it | integration: embed endpoint | embeddings returned | Embedding microservice live; ingestion uses it |
| 11 | **Redis caching** | Response + semantic + embedding cache; TTL + catalog-version invalidation | unit: cache hit/miss; invalidation | repeat query is cached | Cache hit-rate measurable; cost/latency drop |
| 12 | **Auth (Cognito) + per-user isolation** | Cognito + provider-agnostic JWT verify interface; RBAC; tie sessions to authed users; row-level isolation | unit: jwt verify; integration: authz | protected route rejects no-token | Auth works; users see only their data |
| 13 | **Rate limiting + cost controls** | Per-user/IP limits; per-user token budgets; spend kill-switch flag | unit: limiter; integration: 429 | exceed limit → 429; flip kill-switch | Limits + budgets + kill-switch enforced |
| 14 | **Security hardening** | Review-text-as-data sanitization; input/output guardrails; PII log scrubbing | unit: injection blocked; PII scrubbed | injected review can't hijack | Prompt-injection-via-context blocked; logs clean |
| 15 | **Model tiering + fallback** | Router: cheap default → escalate on low confidence → cross-provider fallback | unit: routing; integration: fallback | simulate provider down → fallback | Tiering + outage fallback verified |
| 16 | **Failure-mode degradation** | Circuit breakers, timeouts, retries+jitter on every external call; degrade table behaviors | integration: kill dep → graceful | kill Qdrant/LLM → useful response | Each dependency failure degrades, not crashes |
| 17 | **Observability** | OTel traces + Prometheus metrics; Langfuse LLM tracing + token/cost; dashboards + alerts | smoke: trace emitted | trace + cost visible in Langfuse/Grafana | Full request trace + cost + SLO alerts live |
| 18 | **Frontend (Next.js)** | Next.js + Tailwind/shadcn; streaming chat UX, auth, citation rendering | component + e2e (Playwright) | end-to-end via browser | UI streams, authenticates, shows citations |
| 19 | **Dockerize + compose** | Multi-stage non-root images for every service; `docker-compose.yml` full stack | smoke: compose up healthcheck | `docker compose up` whole system | Entire stack runs in containers locally |
| 20 | **Local K8s (kind) + Helm** | Helm charts; probes, resource limits, HPA, PDB, network policy; secrets via ESO | smoke: pods healthy on kind | `helm install` on kind works | Full stack on local K8s; secrets externalized |
| 21 | **Terraform + cloud infra** | Modules: network/data/cache/eks/qdrant/app/observability; remote state (S3+DynamoDB) | `terraform validate`/`plan` | `terraform plan` clean vs AWS | Plan provisions full stack (no apply yet) |
| 22 | **CI/CD (GitHub Actions)** | lint → unit → integration → **RAGAS gate** → build → push ECR → deploy dev → manual gate → staging | pipeline runs on PR | green pipeline; deploys dev | CI gates quality; CD deploys to dev env |
| 23 | **Load test + tune** | k6 scripts; tune HPA, connection pooling, cache; record p50/p95/p99 + cost | k6 load profiles | hit target RPS within NFRs | NFRs met or gaps documented with numbers |
| 24 | **Docs + runbook** | README, architecture diagram, runbook, ADR links to Decision Log | doc lint | new dev can run + operate | Repo is operable by someone else |

## Why this order
- **Steps 2–6 front-load the real uncertainty:** "does the rewritten pipeline on Qdrant with hybrid+rerank actually retrieve *better*?" We build the **eval harness (5) before the quality change (6)** so improvement is measured, not assumed. If the new retrieval is worse, we find out on day ~5 with full flexibility, not after building infra around it.
- **Abstraction (3) before swaps (4, 10, 12, 15):** every swappable dependency goes behind an interface first, so each later swap is an adapter change, not a rewrite.
- **App correct & observable (7–17) before pretty (18) and before infra (19–23):** no point provisioning EKS for a pipeline whose quality/cost/security isn't proven.
- **Infra last (19–23) because it's laborious-but-predictable**, not uncertain — and because "deployable" through Step 19 means docker-compose, which is enough to verify every prior step.
- **Load test (23) last** because it validates the *whole* assembled system against the Phase 1 NFRs.

## Constraints honored
- Each step = one focused session (~½–1 day).
- Each step ends deployable; tests added in the same step; new code gets tests in-commit, legacy-being-modified gets a characterization test first.
- One step per commit, tagged with the Decision(s) it implements.
