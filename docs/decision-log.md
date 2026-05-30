# Decision Log — P2 Conversational, Rating-aware Product Recommender (Enterprise2)

> **Status:** Phase 2 (Architecture Decisions). Awaiting sign-off before Phase 3 (Transformation Plan).
> **Source project:** `demo/` (Flask + LangChain + AstraDB review-QA chatbot).
> **Output:** repo root (this directory).
> **Build intent:** *Fresh from scratch* — every decision re-derived from the Demo + the Service Packages Build-Spec. After user revisions (Qdrant, DynamoDB, Full LangChain, EKS), the stack now converges with the prior `P2-...-Enterprise/` on the vector DB, orchestration, and compute layers; the deliberate divergences are now the **primary store (DynamoDB)**, **auth (Clerk)**, **queue (ARQ)**, and **A/B (GrowthBook)**.
> **Package mapping:** Build-Spec **Package 1 (Production-grade RAG)** for the serving/grounding/production stack **+ a content-based, rating-aware recommender core** as the package-defining delta.

---

## Non-Functional Targets (the bar every decision is judged against)

| Dimension | Target |
|---|---|
| Scale | 1M MAU · 50k DAU · 2k peak concurrent (read-traffic scale on a small, cache-friendly catalog) |
| Throughput | ~200 RPS sustained query path; burst to ~500 RPS |
| Latency — full (rank + LLM explain) | p50 < 1s · **p95 < 2s** · p99 < 3.5s |
| Latency — ranking-only path | p95 < 300ms |
| Uptime SLO | 99.9% (~43 min/mo error budget) |
| Cost | blended **< $0.005 / query**; cache hit ≥ 60% |
| Compliance | GDPR-aware (right-to-be-forgotten, no PII storage beyond account/session); no HIPAA/SOC2 |
| Team size | 1 (solo operator — ops surface is a first-class constraint) |

---

## Decision 1: Primary database
**Question:** What system of record holds users, sessions, chat history, recommendations, citations, and audit?
**Options considered:**
- **A — DynamoDB (single-table design):** managed KV/document, IRSA auth | Pros: single-digit-ms reads, no connection-pool ceiling at 200 RPS, on-demand scale to 1M MAU, per-partition GDPR delete is clean | Cons: access patterns must be designed up front; no joins/aggregations; analytics weak | Cost: on-demand pay-per-request | Fits scale? **Y**
- **B — Postgres (Aurora Serverless v2):** relational, ACID | Pros: joins, analytics, FTS | Cons: connection-pool limits, vector/FTS advantage now redundant (Qdrant owns both) | Fits? Y but redundant
- **C — MongoDB Atlas:** document store | Pros: flexible schema | Cons: extra vendor, weaker transactions | Fits? Y
**Decision:** **DynamoDB (single-table design).** Chat history via LangChain `DynamoDBChatMessageHistory` (persistent, per-session — fixes the demo's shared in-memory bug). App auth to DynamoDB via **IRSA** (no static creds).
**Reasoning:** Once vectors **and** the hybrid sparse half move to Qdrant (Decision 2), Aurora's vector/FTS advantage disappears and the hot path is pure KV access — user-by-id, session-by-id, messages-by-session — which is DynamoDB's sweet spot: single-digit-ms, no pool exhaustion at 200 RPS, seamless scale to the 1M-MAU target. Single-table models users → sessions → messages → recommendations → citations as item collections under one PK. **Eval/analytics do not live here** — the eval harness runs offline over golden sets (artifacts to S3) and online scores stream to Langfuse/Grafana — so DynamoDB's weak analytics is not a constraint.
**Trade-offs accepted:** Access patterns locked up front; ad-hoc relational queries/joins are hard; no server-side aggregation; evolving access patterns later is costly. *This is the price of the KV-scale + low-ops win.*
**Reversibility:** **Hard** (access-pattern lock). Trigger to revisit: the serving DB needs rich ad-hoc relational analytics, or access patterns stop fitting single-table.

## Decision 2: Vector database
**Question:** Where do product embeddings live for retrieval?
**Options considered:**
- **A — Qdrant (self-host on EKS StatefulSet, or Qdrant Cloud):** OSS, scales 100M+, native hybrid (dense+sparse), rich payload filtering | Pros: removes any vector-count ceiling; payload holds avg_rating/review_count/ACL for ranking; self-host on K8s exercises real vector-DB ops | Cons: a stateful service to run (PVCs, replication, snapshots, upgrades) | Cost: self-host ~node cost, or Qdrant Cloud ~$25–80/mo | Fits scale? **Y**
- **B — pgvector (in Aurora):** vectors as a Postgres column | Pros: zero new infra, SQL joins | Cons: ~5M-vector ceiling; ties us to keeping Postgres | Fits? Y but capped
- **C — Pinecone:** fully managed | Pros: zero ops | Cons: paid floor, vendor lock, less flexible hybrid | Fits? Y but expensive
**Decision:** **Qdrant** (1536-d, cosine; dense + sparse named vectors for hybrid; `langchain-qdrant` `QdrantVectorStore`). Self-hosted as an EKS StatefulSet (Qdrant Cloud as the managed fallback).
**Reasoning:** Native hybrid + payload filtering let us store `avg_rating`/`review_count` alongside vectors and feed the rating-aware ranking (Decision 3); scaling to 100M+ removes the ceiling pgvector would have imposed; self-hosting on K8s is the thing that actually closes the *production vector-DB ops* gap (StatefulSet, replication, snapshot/restore). Decoupling vectors from the primary store is precisely what frees Decision 1 to be DynamoDB.
**Trade-offs accepted:** A stateful service to operate (the single biggest ops item we're taking on); ranking is now app-side over Qdrant payload, not a single SQL join.
**Reversibility:** **Moderate** — kept behind a `VectorStore`/LangChain-retriever interface; Pinecone/pgvector swap is mechanical. Trigger: ops burden of self-hosted Qdrant outweighs benefit → move to Qdrant Cloud.

## Decision 3: RAG/Agentic paradigm + retrieval strategy
**Question:** What is the shape of the inference pipeline?
**Options considered:**
- **A — Naive RAG (demo's):** dense top-k → stuff → LLM | Cons: ignores ratings, no hybrid, no ranking | Fits? N
- **B — Hybrid + rating-aware ranking + (optional) rerank + RAG explanation** | Fits? **Y**
- **C — Agentic (LangGraph + tools):** | Cons: latency/reliability/cost; out-of-scope | Fits? N
**Decision:** **Qdrant hybrid retrieval (dense+sparse) → app-side rating-aware ranking → optional rerank → grounded RAG explanation**, with history-aware query rewriting. **Orchestrated with LangChain** (history-aware retriever + LCEL chain).
**Reasoning:** Exactly what "true recommender on review data" requires. Qdrant's **native hybrid** replaces the old pgvector+Postgres-FTS combo (cleaner, one store). The ranking blend `f(semantic, avg_rating, review_volume)` now runs in **application code** (`packages/recommender`) over Qdrant results + payload — better separation than burying it in SQL, and it's the part that *is* the recommender. Reranker (bge-reranker) stays behind a flag — lift unproven at <30 products, measure first.
**Trade-offs accepted:** We own the score function (no framework ranks for us); two LLM calls/turn (rewrite cached).
**Reversibility:** Easy to add multi-query/HyDE/agentic later behind the same LangChain chain + API contract.

## Decision 4: LLM provider + tiering
**Question:** Which model(s) answer, and how do we tier for cost/quality?
**Options considered:**
- **A — Groq (Llama-3.3-70b) primary + OpenAI (gpt-4o) escalation** | Pros: ~10× cheaper & faster, demo familiarity | Cons: provider maturity, peak rate limits | Fits? **Y**
- **B — OpenAI gpt-4o-mini primary + gpt-4o escalation** | Pros: reliability, mature tooling | Cons: ~3× Groq cost | Fits? Y
- **C — Anthropic Claude Haiku 4.5 + Sonnet 4.6** | Pros: instruction-following, citations | Cons: latency > Groq | Fits? Y
- **D — Bedrock multi-model** | Pros: AWS-native, provisioned throughput | Cons: indirection | Fits? Y
**Decision:** **Groq Llama-3.3-70b primary; OpenAI gpt-4o escalation; Anthropic Sonnet 4.6 second fallback** — behind LangChain chat-model interfaces (`langchain-groq`, `langchain-openai`, `langchain-anthropic`) with a runtime fallback chain.
**Reasoning:** ~80 LLM RPS post-cache → cost dominates; Groq leads price/speed; escalation catches the hard ~5–10%; two-provider fallback prevents single-provider-outage = full-outage.
**Trade-offs accepted:** Three providers/error paths; Groq peak limits need queue+retry (Decision 11).
**Reversibility:** Easy behind LangChain `with_fallbacks`. Trigger: Groq reliability < 99.5% or quality below gate.

## Decision 5: Embedding model
**Question:** What produces query/product vectors? *(Locked, unchanged.)*
**Options considered:**
- **A — OpenAI `text-embedding-3-small` (1536-d)** | Pros: cheap, fast, no infra, natively 1536-d (matches Qdrant config) | Cons: vendor lock | Fits? **Y**
- **B — Cohere embed-english-v3 (1024-d)** | Pros: quality | Cons: extra vendor | Fits? Y
- **C — BGE-large self-hosted** | Pros: $0 marginal, residency | Cons: GPU node + cold starts | Fits? Y but overkill
**Decision:** **OpenAI `text-embedding-3-small` @ 1536-d** (`langchain-openai` `OpenAIEmbeddings`). Qdrant collection configured to 1536-d cosine.
**Reasoning:** Embedding cost is rounding error at this catalog; 1536-d gives strong recall without bloating Qdrant's HNSW; no infra wins at this stage.
**Trade-offs accepted:** Vendor lock; version migration = re-embed (cheap now, real at 1M).
**Reversibility:** Moderate — embeddings versioned in the collection; re-embed is one ARQ job. Trigger: residency need or > 50M tokens/mo.

## Decision 6: Orchestration framework
**Question:** LangChain / LlamaIndex / LangGraph / thin custom?
**Options considered:**
- **A — Full LangChain (LCEL):** chains, retrievers, memory, integrations | Pros: rich first-party integrations (Qdrant, Groq, OpenAI, DynamoDB chat history), demo continuity, native Langfuse callback, marketable skill | Cons: quarterly API churn, abstraction overhead, harder low-level tracing | Fits? **Y**
- **B — Thin custom (Pydantic + SDKs):** | Pros: full control, no churn | Cons: re-implement retrievers/memory/integrations LangChain already provides | Fits? Y
- **C — LlamaIndex** | Pros: retrieval primitives | Cons: second framework alongside the demo's LangChain | Fits? Partially
- **D — LangGraph** | Cons: overkill for a fixed pipeline | Fits? N
**Decision:** **Full LangChain (LCEL).** `QdrantVectorStore` retriever + `create_history_aware_retriever` + `create_retrieval_chain`; memory via `RunnableWithMessageHistory` backed by **`DynamoDBChatMessageHistory`** (persistent, per-session); provider fallback via `with_fallbacks`; **isolated behind our own service interfaces** so it can be swapped.
**Reasoning:** With Qdrant + DynamoDB + multi-provider all having first-party LangChain integrations, LangChain now buys real wiring (Qdrant retriever, DynamoDB-backed history, provider fallback, Langfuse callback) instead of just abstraction. Continuity with the demo (already LangChain) lowers migration risk. We accept the churn cost and contain it by pinning versions and keeping LangChain behind interfaces.
**Trade-offs accepted:** Framework lock + churn maintenance; less control over exact retry/parsing internals; must pin versions defensively.
**Reversibility:** Moderate — interfaces isolate it; swapping to thin-custom/LlamaIndex later is contained.

## Decision 7: Backend language + framework + API style
**Question:** What serves the API?
**Options considered:**
- **A — Python + FastAPI (async, Pydantic v2)** | Pros: matches your stack + Python LLM/eval ecosystem + LangChain is Python-native; async fine at 200 RPS | Cons: GIL (irrelevant, I/O-bound) | Fits? **Y**
- **B — Node + NestJS/Hono** | Pros: shared TS w/ FE | Cons: LangChain.js less mature, weaker eval ecosystem | Fits? Y
- **C — Go + chi/Echo** | Pros: raw throughput | Cons: no LangChain, weakest LLM ecosystem | Fits? Y but costly
**Decision:** **Python 3.12 + FastAPI**, REST + **SSE** streaming (LangChain `astream_events` → SSE); no GraphQL/gRPC.
**Reasoning:** Bottleneck is the LLM call, not Python; LangChain + RAGAS + promptfoo + embeddings clients all live in Python; SSE is the right chat-streaming primitive.
**Trade-offs accepted:** Higher memory than Go/Rust; mitigated by warm pool.
**Reversibility:** Hard to swap language; easy to front with a Go gateway later.

## Decision 8: Frontend + streaming UX
**Question:** Web framework + streaming/cancel handling.
**Options considered:**
- **A — Next.js App Router (TS, Tailwind, shadcn/ui)** | Pros: SSR, first-class streaming, ecosystem | Cons: build complexity | Fits? **Y**
- **B — Remix** | Pros: simpler model | Cons: smaller ecosystem | Fits? Y
- **C — SvelteKit** | Pros: small bundle | Cons: smaller community for portfolio narrative | Fits? Y
- **D — Streamlit** | Cons: not prod per build-spec | Fits? **N**
**Decision:** **Next.js (App Router, TS, Tailwind, shadcn/ui).** SSE streaming: recommendation cards render first, explanation streams below; `AbortController` cancel; optimistic user message.
**Reasoning:** Cards-before-explanation is the biggest perceived-latency win at 2s p95; Next.js + SSE supports it cleanly; strongest portfolio narrative.
**Trade-offs accepted:** Next.js build complexity vs simpler frameworks.
**Reversibility:** Easy — FE independent of API contract.

## Decision 9: Authentication / authorization
**Question:** Who handles login, sessions, per-user isolation?
**Options considered:**
- **A — Clerk** | Pros: 1-day integration, hosted UI/MFA/social, free ≤10k MAU | Cons: paid above, vendor | Fits? **Y**
- **B — AWS Cognito** | Pros: $0 floor, IAM integration | Cons: clunky DX, custom UI | Fits? Y
- **C — Supabase Auth** | Pros: Postgres-native, OSS | Cons: extra service | Fits? Y
- **D — Auth.js (NextAuth)** | Pros: free, in-app | Cons: more code, DIY MFA | Fits? Y
**Decision:** **Clerk.** JWT verified in FastAPI middleware; **user id scopes every DynamoDB partition key** + session.
**Reasoning:** Single-tenant consumer app, speed-to-portfolio matters, Clerk eats password/MFA/social complexity; free tier covers demo + early traction; documented Cognito migration path.
**Trade-offs accepted:** Vendor; ~$20k/mo at 1M *real* MAU — but we design-for, not run-at, that scale.
**Reversibility:** Moderate (JWT + `UserService` abstraction). Trigger: >10k *real* MAU or SAML/SCIM needed.

## Decision 10: Caching strategy
**Question:** What gets cached, where, invalidated how?
**Options considered:**
- **A — 4-layer (in-proc LRU + Redis embedding + Qdrant semantic + Redis response)** | Pros: hits 60%+ target; semantic cache is the big lever | Cons: 4 layers to monitor | Fits? **Y**
- **B — Response cache only** | Pros: simple | Cons: ~30% hit (misses near-dupes) | Fits? Partially
- **C — CDN + Redis embedding** | Cons: user-scoped chat → poor CDN cacheability | Fits? N
**Decision:** **4-layer.** L0 in-proc LRU (catalog meta from DynamoDB, 60s) · L1 Redis embedding cache (30d) · **L2 semantic cache as a dedicated Qdrant collection** (NN on query embedding, ~0.97 cosine, 1h, per-user) · L3 Redis response cache (10m). Invalidation by **catalog_version tag** (atomic bump). Singleflight to prevent stampede.
**Reasoning:** Tiny catalog + repetitive queries → very high semantic-cache hit; at 60% we hit cost target, at 80% we double it. **L2 lives in Qdrant** because we already run it and ElastiCache (Redis OSS) lacks the RediSearch module needed for Redis-native vector search — using Qdrant for the semantic-cache collection is the clean, no-new-infra fix.
**Trade-offs accepted:** 4 layers to monitor; stampede risk mitigated by request coalescing.
**Reversibility:** Easy — each layer measured, removable.

## Decision 11: Queue / async work
**Question:** What runs ingestion, re-embedding, eval, periodic jobs?
**Options considered:**
- **A — ARQ (async Redis queue)** | Pros: async-native FastAPI fit, light | Cons: no workflow engine, fewer integrations | Fits? **Y**
- **B — Celery + Redis** | Pros: industry default | Cons: sync-rooted, already known (low learning) | Fits? Y
- **C — SQS + workers** | Pros: cloud-native | Cons: more infra | Fits? Y
- **D — Temporal** | Cons: heavyweight | Fits? N
**Decision:** **ARQ + Redis**, workers as an **EKS Deployment autoscaled by KEDA** (`ScaledObject` on Redis queue depth). *Divergent from demo/Celery.*
**Reasoning:** Modest async needs; ARQ is just enough and async-native; divergent learning vs Celery you already know. KEDA is the EKS-native queue-driven autoscaler (replaces what would have been ECS target-tracking).
**Trade-offs accepted:** Less mature; some integrations DIY.
**Reversibility:** Easy — task fns framework-agnostic; SQS swap mechanical.

## Decision 12: Inference serving
**Question:** Hosted APIs vs self-hosted (vLLM/TGI/SageMaker/Bedrock)?
**Options considered:**
- **A — Hosted APIs (Groq + OpenAI + Anthropic)** | Pros: zero infra, no cold start/GPU | Cons: per-token cost, rate limits | Fits? **Y**
- **B — vLLM on EKS GPU pool** | Pros: cost win at high steady QPS | Cons: GPU ops, premature | Fits? Y but premature
- **C — Bedrock** | Pros: AWS-native, IAM, provisioned | Cons: indirection | Fits? Y
- **D — SageMaker endpoints** | Cons: higher cost than direct APIs | Fits? N
**Decision:** **Hosted APIs (Groq → OpenAI → Anthropic)** via LangChain chat models.
**Reasoning:** Self-host pays off only > ~500 QPS on a fixed model; we're ~80 LLM RPS post-cache — GPU economics lose. *Note:* since we now run EKS (Decision 15), adding a **vLLM GPU node pool** later is a natural extension if volume justifies it.
**Trade-offs accepted:** Token cost scales with traffic; capped by Decision 20.
**Reversibility:** Easy. Trigger: $/q > target×1.5 AND sustained QPS > 500 → add vLLM on an EKS GPU node group.

## Decision 13: Observability stack
**Question:** App-level (traces/metrics/logs) + LLM-specific tracing.
**Options considered:**
- **A — OTel → Grafana Cloud (Prom+Loki+Tempo) + self-host Langfuse (on EKS)** | Pros: one OTel SDK; Grafana free tier; Langfuse has a **native LangChain callback handler** | Cons: two backends | Fits? **Y**
- **B — CloudWatch + X-Ray + LangSmith** | Pros: AWS-native, LangChain-native | Cons: weak dashboards; LangSmith managed (cost) | Fits? Y
- **C — DataDog** | Pros: best dashboards | Cons: $$$ | Fits? Y but expensive
**Decision:** **OTel → Grafana Cloud (app); self-host Langfuse on EKS (LLM)**, wired via the **LangChain `CallbackHandler`** (near-zero glue). Trace ID links a Grafana request trace to its Langfuse LLM trace.
**Reasoning:** Instrument once, pick backends independently; free tiers cover portfolio; the LangChain callback makes per-request retrieval/rerank/generation cost+latency+token capture almost free — the thing demo's broken Counter failed to do.
**Trade-offs accepted:** Two backends; Langfuse is a stateful service to operate (now alongside Qdrant on EKS).
**Reversibility:** Easy — OTel exporters pluggable.

## Decision 14: Cloud provider + core services
**Question:** Which cloud + services?
**Options considered:**
- **A — AWS** (your background, build-spec default) | Pros: skill-audit match, biggest hiring market | Cons: ops complexity | Fits? **Y**
- **B — GCP** | Pros: GKE Autopilot, Cloud Run | Cons: smaller market for you | Fits? Y
- **C — Azure** | Pros: enterprise-friendly | Cons: weakest background match | Fits? Y
**Decision:** **AWS.** **EKS** (compute) · **DynamoDB** (primary) · **Qdrant on EKS** (vector) · **ElastiCache Redis** (cache + queue + L1/L3) · **S3** (CSV, eval artifacts, Qdrant snapshots, Langfuse blobs, backups) · **CloudFront** (Next.js static) · **ALB** (via AWS Load Balancer Controller) · **Route 53** · **ECR** · **Secrets Manager + KMS** (via External Secrets Operator) · **CloudWatch** (OTel sink + alarms) · **WAF**. EKS add-ons: managed node groups + **Karpenter/cluster-autoscaler**, **KEDA**, **EBS CSI** (Qdrant PVCs), **AWS Load Balancer Controller**, **External Secrets Operator**, **ArgoCD**.
**Reasoning:** Hiring market + skill audit point AWS; service picks are the boring-correct combination for a DynamoDB + Qdrant + EKS stack.
**Trade-offs accepted:** AWS billing complexity; the EKS add-on surface is the bulk of our ops burden.
**Reversibility:** Hard.

## Decision 15: Container, orchestration, IaC
**Question:** How is compute deployed?
**Options considered:**
- **A — EKS (managed K8s)** | Pros: closes the explicit *Production Kubernetes* gap (node groups, autoscaler, KEDA, PDBs, multi-AZ); portable; GPU-ready; Qdrant StatefulSet exercises stateful-K8s ops | Cons: cluster/node/upgrade + add-on ops = highest solo-ops burden | Fits? **Y**
- **B — ECS Fargate + Terraform** | Pros: zero node ops, per-task IAM | Cons: no GPU; doesn't exercise the K8s gap; awkward for self-hosted Qdrant StatefulSet | Fits? Y but shallower learning
- **C — Cloud Run** | Cons: implies GCP | Fits? (see D14)
- **D — Lambda** | Cons: cold start breaks p95<2s streaming; bad fit for stateful Qdrant | Fits? **N**
**Decision:** **EKS (managed node groups, CPU).** Components: `api` (Deployment + HPA), `web` (Deployment), `worker` (Deployment + KEDA), `qdrant` (StatefulSet + PVC + replicas), `langfuse` (Deployment). **Helm** charts; **ArgoCD** GitOps; **Argo Rollouts** canary; **AWS LB Controller** (ALB ingress); **KEDA**; **External Secrets Operator**; **Karpenter/cluster-autoscaler**. **Terraform** modules: `vpc, eks, dynamodb, qdrant, redis, s3, cloudfront, waf, observability`.
**Reasoning:** EKS closes the biggest single gap in the skill audit (*Production Kubernetes* — node groups, cluster-autoscaler, KEDA, PDBs, multi-AZ), is required to run self-hosted Qdrant (Decision 2) as a StatefulSet properly, and is GPU-ready for a future vLLM tier (Decision 12). It is the deliberate choice to take on more ops in exchange for the most resume-relevant, gap-closing infrastructure work.
**Trade-offs accepted:** Highest ops surface of any compute option — cluster upgrades, node-group management, and the KEDA/ArgoCD/LB-controller/ESO add-on stack to secure and maintain; higher always-on monthly floor (EKS control plane ~$73/mo + node groups + Qdrant nodes + NAT) than serverless — though per-query cost is still LLM-dominated, so the $0.005/q target holds.
**Reversibility:** Moderate→Hard (containers portable; IaC + K8s manifests are real rework). Trigger to simplify: solo-ops burden proves unsustainable → fall back to ECS Fargate + Qdrant Cloud.

## Decision 16: CI/CD pipeline
**Question:** Tool, stages, environments, promotion, rollback.
**Options considered:**
- **A — GitHub Actions + OIDC→AWS, deploy via ArgoCD + Argo Rollouts** | Pros: no keys (OIDC); GitOps + canary auto-rollback native to EKS | Cons: ArgoCD is another service | Fits? **Y**
- **B — GitHub Actions + CodeDeploy** | Cons: CodeDeploy blue/green is ECS/EC2-shaped, not the EKS-native pattern | Fits? worse on EKS
- **C — Jenkins** | Cons: ops burden, already done | Fits? N
**Decision:** **GitHub Actions + OIDC; deploy via ArgoCD (GitOps) + Argo Rollouts (canary).** Envs: dev (auto on `main`), staging (tag `staging-*`), prod (manual approve, tag `vX.Y.Z`). Stages: lint+type → unit → integration (real DynamoDB-local + Qdrant + Redis in compose) → build+Trivy → ECR → tf plan → tf apply → **eval gate (RAGAS+ranking)** → ArgoCD sync → Argo Rollouts canary with Prometheus/CloudWatch analysis → auto-rollback on failed analysis / 5xx spike.
**Reasoning:** OIDC = no keys in CI; ArgoCD + Argo Rollouts is the EKS-native progressive-delivery pattern (replaces the ECS-shaped CodeDeploy) and closes the *GitOps/canary* gap; eval gate makes RAG "production-grade" not just "deployed."
**Trade-offs accepted:** ArgoCD/Argo-Rollouts add to the cluster surface.
**Reversibility:** Easy.

## Decision 17: Secrets & configuration
**Question:** Where secrets live, rotation, per-env config.
**Options considered:**
- **A — Secrets Manager + SSM Param Store + External Secrets Operator + Pydantic Settings** | Pros: AWS-native, KMS, IAM-scoped, ESO syncs to K8s Secrets, RDS-style rotation | Cons: ESO is another controller | Fits? **Y**
- **B — Vault** | Pros: gold standard | Cons: another service | Fits? Y but heavy
- **C — `.env` + GitHub Secrets** | Cons: not prod-grade for shared infra | Fits? N
**Decision:** **Secrets Manager** (secrets) + **SSM Param Store** (config) + **External Secrets Operator** (syncs SM → K8s Secrets) + **Pydantic Settings** (typed load). DynamoDB/Qdrant access via **IRSA** (no static creds). KMS CMK per env.
**Reasoning:** ESO is the EKS-native way to get Secrets Manager values into pods without baking creds; IRSA gives the app a scoped IAM role for DynamoDB; Pydantic Settings type-checks the env contract at the boundary.
**Trade-offs accepted:** ESO controller to operate; ~$0.40/secret/mo × ~10/env.
**Reversibility:** Easy.

## Decision 18: Security posture / threat model
**Question:** Which threats matter, mitigated how?
**Decision (threat model → mitigation):**
- **Prompt injection via reviews (med):** system prompt ignores retrieved-content directives; **LangChain `with_structured_output`** enforces JSON for the rec list (only explanation free-form); schema validation; adversarial test fixtures.
- **PII in logs (high):** Presidio scrubber pre-emission; query hashed for correlation; raw text only in Langfuse (redacted, short retention).
- **Jailbreaks/output abuse (low):** output filter + denylist; adversarial eval suite.
- **DDoS/abuse (med):** WAF managed rules + rate limit; per-user Redis token bucket; per-IP fallback; kill switch (D20).
- **Auth bypass (high):** Clerk JWT via JWKS rotation; all paths authed except `/health`; CORS locked; SameSite cookies; SSE authed + per-token concurrency cap.
- **Secret exposure (high):** Secrets Manager + ESO + IRSA only; gitleaks pre-commit; Trivy + dep audit in CI.
- **Supply-chain (med):** lockfiles, Dependabot, Trivy, distroless base; **pin LangChain versions** (churn = security/behavior drift).
- **Residency (low):** DynamoDB/Qdrant/Redis/S3 region-pinned; documented.
**Reversibility:** Ongoing — reviewed each major release.

## Decision 19: Evaluation strategy *(Locked, unchanged.)*
**Question:** Offline + online eval, golden sets, regression, A/B.
**Decision:**
- **Ranking eval (package-defining):** golden `(query → relevant/irrelevant product_ids)`, ~50 queries. **Recall@5, NDCG@5, MRR.** CI gate blocks merge on regression vs `main`.
- **RAG eval:** **RAGAS** (faithfulness, answer-relevancy, context-precision); judge = Claude Sonnet (off-family to cut shared bias). Provisional gate: faithfulness ≥ 0.90, answer-relevancy ≥ 0.85 — **re-baselined after first measurement.**
- **Prompt regression:** **promptfoo** on `packages/core/prompts/` changes.
- **Online eval:** sample 1% prod, async judge, scores → Langfuse + Grafana, alert on drift.
- **A/B:** **GrowthBook** (OSS self-host), prompt/model variants, guardrail metrics (latency/cost/eval).
**Reasoning:** Ranking eval is the recommender's core quality signal; RAGAS is package standard; promptfoo catches prompt-only regressions; GrowthBook is the experimentation backbone (new for you).
**Trade-offs accepted:** Golden-set curation is real, non-skippable work.
**Reversibility:** Easy.

## Decision 20: Cost controls
**Question:** How to keep the bill bounded?
**Decision:**
- **Per-request:** `max_tokens=600`, `max_retrieval_k=10`, `max_rerank_k=5`, cached query embedding, rewrite call ≤80 tokens + cached.
- **Per-user:** token bucket — 30 msg/5min, 200/day anon, 500/day signed-in; 429 + `Retry-After`.
- **Kill switch:** GrowthBook flag `llm_enabled` → 503 + degraded UX; cache still served.
- **Routing:** Groq primary; escalate to gpt-4o only on low-confidence/refusal/short-response (<10% target).
- **Monitoring:** Langfuse $/req; CloudWatch composite alarm (`cost/hr` high); Slack/PagerDuty; daily budget summary; per-layer cache ROI dashboard.
- **Infra cost note:** EKS adds an always-on monthly floor (control plane + nodes + Qdrant); tracked separately from per-query cost.
**Reversibility:** Easy — all config.

## Decision 21: Failure modes & degradation
**Question:** What does the user see when each dependency fails?
**Decision:**
| Failure | Behavior | Mechanism |
|---|---|---|
| Groq down | Escalate OpenAI → Anthropic | LangChain `with_fallbacks` + circuit breaker (5 fail/30s → trip 60s) |
| All LLMs down | Ranked products + static template explanation + banner | Pre-baked per-product template |
| DynamoDB throttling | Exponential backoff + on-demand capacity; serve cached catalog/session snapshot; queue writes | SDK adaptive retries + bulkhead |
| Qdrant down/slow (p95>250ms) | **Popularity-only ranking** from DynamoDB catalog cache (rating+volume, no vector) | Latency circuit breaker |
| Redis down | Pass-through (cold) to source stores; bulkhead caps concurrency | Tenacity + bulkhead |
| Retrieval empty | "No good match" + offer top-rated | API-level (F6) |
| Embedding API down | Use cached embedding else 503 retry | Embedding cache (L1) |
| Clerk JWKS down | Cached JWKS valid 1h, then reject | JWT lib |
| Malicious input | Reject + audit + counter | D18 |
**Reversibility:** Easy to tune thresholds.

## Decision 22: Repo structure
**Question:** Mono/poly repo, boundaries, layout.
**Decision:** **Monorepo at repo root.** `demo/` untouched (reference), `old/` archived (ignored), `Prompts/` source docs. New layout:
```
/
├── apps/{web, api, ingestion}
├── packages/{core, retrieval, recommender, eval}
│     retrieval/ → LangChain QdrantVectorStore retriever + hybrid config
│     recommender/ → app-side rating-blend ranking over Qdrant payload
├── infra/{terraform, compose}
│     terraform modules: vpc, eks, dynamodb, qdrant, redis, s3, cloudfront, waf, observability
│     compose: DynamoDB-local + Qdrant + Redis + Langfuse for local dev
├── ops/{langfuse, grafana, argocd, helm}
├── .github/workflows/
├── tests/{unit, integration, e2e, load}
└── docs/
```
**Reasoning:** One PR per cross-cutting change; `packages/*` boundary enforces import discipline (apps import packages, never each other).
**Reversibility:** Moderate.

## Decision 23: Region / DR strategy
**Question:** Single vs multi-region; backup/restore.
**Options considered:**
- **A — Single-region Multi-AZ** | Pros: simple, meets 99.9% | Cons: region outage = outage | Fits? **Y**
- **B — Multi-region active-passive** | Pros: 99.95%+ | Cons: 2–3× cost | Fits? Y but overspec
- **C — Multi-region active-active** | Cons: ~5× cost, conflicts | Fits? N
**Decision:** **Single-region Multi-AZ.** EKS node groups across AZs; Qdrant StatefulSet with replicas across AZs; Redis replicas across AZs. Backups: **DynamoDB PITR (35-day) + on-demand backups**; **Qdrant snapshots → S3 (scheduled ARQ job)**; S3 versioning + 30d lifecycle; Langfuse store snapshotted. Restore drill in runbook, run quarterly in staging.
**Reasoning:** 99.9% = 43 min/mo; AZ-failover clears it; multi-region is for 99.95%+. **DynamoDB Global Tables** make a future multi-region step nearly turnkey; IaC is region-templated.
**Reversibility:** Hard, but cheap to defer (Global Tables ease it).

## Decision 24: Privacy / data deletion (GDPR-aware)
**Question:** How to delete user data on request?
**Decision:**
- **What is personal data:** user account + sessions + messages + recommendations, all in **DynamoDB**. (Qdrant holds *catalog* product embeddings — **not** personal data — so it's untouched by user deletion.)
- **Account deletion:** Clerk webhook → ARQ job → **query DynamoDB by user PK + batch-delete the item collection** (clean single-partition op); purge from Langfuse + logs within the 30-day GDPR window.
- **Chat TTL:** DynamoDB **TTL attribute** auto-expires messages at 90d; "clear history" triggers the batch-delete synchronously.
- **PII in logs:** D18 scrubber; 30d retention.
- **Audit:** deletions logged to S3 with object-lock 1y.
- **DSAR:** admin endpoint exports the user's DynamoDB item collection as JSON; documented in runbook.
**Reversibility:** Policy-level, easy.

---

## Decision Summary (at-a-glance)

> **Legend.** **Prod-grade?** — Y = production-correct as designed; Y\* = production-correct *with a named caveat* (cost/scale ceiling). **Gap closed** references the skill-audit gap list in `Prompts/01-career-assessment.md`. **Diverges?** — differs from the prior `P2-...-Enterprise/` build.

| # | Decision | Options (✓ = picked) | Pick | Why (1-line) | Prod-grade? | Skill-audit gap it closes | Reversibility | Diverges? |
|---|---|---|---|---|---|---|---|---|
| 1 | Primary DB | ✓DynamoDB · Aurora PG · Mongo Atlas | **DynamoDB (single-table)** | KV hot-path, single-digit-ms, no conn-pool ceiling, scales to 1M MAU | Y | **NoSQL/DynamoDB single-table modeling** + AWS depth | Hard | **Yes (was Postgres)** |
| 2 | Vector DB | ✓Qdrant · pgvector · Pinecone | **Qdrant (EKS StatefulSet)** | 100M+ scale, native hybrid + payload, real vector-DB ops | Y | **Production vector-DB ops + hybrid at scale** | Moderate | — (matches prior) |
| 3 | RAG shape | Naive · ✓Hybrid+rank+RAG · Agentic | **Qdrant hybrid + app-side rating-rank + RAG explain** | The actual recommender; Qdrant native hybrid; LangChain chain | Y | Advanced retrieval (hybrid/rerank) | Easy | New (reframe) |
| 4 | LLM + tiering | ✓Groq→OAI→Anthropic · OAI-only · Claude-only · Bedrock | **Groq → gpt-4o → Sonnet** (LangChain `with_fallbacks`) | Cost/speed leader + fallback = no single-provider outage | Y | Model routing/tiering, fallback chains | Easy | Chain (demo: Groq-only) |
| 5 | Embeddings | ✓OpenAI 3-small@1536 · Cohere v3 · BGE self-host | **text-embedding-3-small @1536** | Cost trivial; natively 1536-d = Qdrant config; no infra | Y | Embedding versioning | Moderate | (demo: HF endpoint) |
| 6 | Orchestration | ✓Full LangChain · thin custom · LlamaIndex · LangGraph | **Full LangChain (LCEL)** | First-party Qdrant/provider/DynamoDB-history integrations + demo continuity + Langfuse callback | Y | (continuity; already a strength) | Moderate | — (matches prior) |
| 7 | Backend | ✓FastAPI · NestJS/Hono · Go | **Python 3.12 + FastAPI + SSE** | Bottleneck is LLM not Python; LangChain+eval are Python | Y | (strength — reinforced) | Hard | — |
| 8 | Frontend | ✓Next.js · Remix · SvelteKit · ~~Streamlit~~ | **Next.js App Router + SSE** | Cards-first streaming = biggest perceived-latency win | Y | Streaming UX (cancel/optimistic) | Easy | (demo: Flask/Jinja) |
| 9 | Auth | ✓Clerk · Cognito · Supabase · Auth.js | **Clerk** | Eats MFA/social/password; free ≤10k MAU | Y\* ($ at 1M MAU) | Authn/authz at depth (OAuth2/OIDC/JWT) | Moderate | **Yes (was Cognito)** |
| 10 | Caching | ✓4-layer · response-only · CDN+Redis | **4-layer (LRU+Redis embed+Qdrant semantic+Redis response)** | Semantic cache = cost lever; L2 in Qdrant (no RediSearch on ElastiCache) | Y | **Semantic caching as a system** (explicit gap) | Easy | New |
| 11 | Queue | ✓ARQ · Celery · SQS · Temporal | **ARQ + Redis (KEDA on EKS)** | Async-native, just-enough; KEDA queue-depth autoscale | Y | Async work + **KEDA event-driven scaling** | Easy | **Yes (was Celery)** |
| 12 | Inference serving | ✓Hosted APIs · vLLM · Bedrock · SageMaker | **Hosted APIs** (vLLM-on-EKS ready) | Self-host loses < 500 QPS; we're ~80 RPS post-cache | Y | Knowing *when not* to self-host | Easy | — |
| 13 | Observability | ✓OTel+Grafana+Langfuse · CW+X-Ray+LangSmith · DataDog | **OTel→Grafana + Langfuse on EKS** | Instrument once; LangChain callback → near-free LLM traces | Y | **Observability + LLM tracing** (explicit gap) | Easy | — |
| 14 | Cloud | ✓AWS · GCP · Azure | **AWS** | Skill-audit + hiring-market match | Y | AWS depth (VPC/IAM/services) | Hard | — |
| 15 | Compute/IaC | ✓EKS · ECS Fargate · Cloud Run · ~~Lambda~~ | **EKS + Terraform + Helm/ArgoCD** | Closes biggest gap; runs Qdrant StatefulSet; GPU-ready | Y | **Production Kubernetes** (explicit, large gap) | Mod→Hard | — (matches prior) |
| 16 | CI/CD | ✓GH Actions+OIDC+ArgoCD/Rollouts · GH+CodeDeploy · ~~Jenkins~~ | **GH Actions + ArgoCD + Argo Rollouts canary** | No keys (OIDC); EKS-native GitOps + canary; eval gate | Y | **Progressive delivery, GitOps** (explicit gap) | Easy | — |
| 17 | Secrets/config | ✓SecretsMgr+SSM+ESO+Pydantic · Vault · ~~.env~~ | **Secrets Manager + ESO + IRSA + Pydantic Settings** | KMS, IAM-scoped, ESO→K8s Secrets, no static creds | Y | **Secrets management** (explicit gap) | Easy | — |
| 18 | Security | threat-model (not a tool pick) | **8-threat model + mitigations** | Reviews=untrusted; PII scrub; WAF; JWT; supply-chain | Y | **Security/compliance for AI** (explicit gap) | Ongoing | — |
| 19 | Evaluation | ✓Ranking+RAGAS+promptfoo+GrowthBook | **Ranking gate + RAGAS + promptfoo + GrowthBook A/B** | Eval is what separates demo from trustable system | Y | **Eval frameworks + A/B** (explicit gap) | Easy | GrowthBook new |
| 20 | Cost controls | per-req caps + tier routing + kill switch | **Caps + routing + kill switch + $ alarms** | < $0.005/q only holds with hard caps + caching | Y | **Cost engineering** (explicit gap) | Easy | — |
| 21 | Failure modes | per-dependency degradation matrix | **Circuit breakers + named fallbacks** | Every external is breaker-able w/ user-visible fallback | Y | **Distributed-systems patterns** (explicit gap) | Easy | — |
| 22 | Repo structure | ✓Monorepo · polyrepo | **Monorepo (apps/packages/infra)** | One PR per cross-cutting change; import discipline | Y | Code org / package boundaries | Moderate | — |
| 23 | Region/DR | ✓1-region MultiAZ · MR a-p · MR a-a | **Single-region Multi-AZ + DynamoDB PITR + Qdrant snapshots** | Clears 99.9%; Global Tables ease future multi-region | Y | DR, backup/restore drill, SLO sizing | Hard | — |
| 24 | Privacy/GDPR | partition-delete + TTL + DSAR | **DynamoDB partition delete + TTL + DSAR export** | Right-to-be-forgotten + audit + retention | Y | **Compliance in practice** (explicit gap) | Easy | — |

### Coverage check — which explicit skill-audit gaps this build closes

| Gap-list item (doc 01 §3) | Closed by Decision(s) |
|---|---|
| **Production Kubernetes** (EKS, node groups, cluster-autoscaler, KEDA, PDBs, multi-AZ) | **15, 11, 16** |
| Production vector-DB ops (sharding, replication, reindexing, hybrid at scale) | 2, 3 (stronger now — self-hosted Qdrant StatefulSet) |
| **NoSQL / DynamoDB single-table data modeling** | **1** |
| Semantic caching as engineered system | 10 |
| Model routing/tiering, fallback chains | 4, 20, 21 |
| Observability (OTel end-to-end) + LLM observability (Langfuse) | 13 |
| Eval frameworks (RAGAS/promptfoo) + A/B + regression in CI | 19, 16 |
| Cost engineering (token budgets, kill switch, unit economics) | 20 |
| Security/compliance (prompt injection, PII redaction, secrets) | 17, 18 |
| Distributed-systems patterns (circuit breakers, bulkheads, backpressure) | 21 |
| Progressive delivery / GitOps / canary | 16 |
| AWS depth (VPC, IAM/IRSA, managed services) | 1, 14, 15, 17 |
| Compliance in practice (right-to-be-forgotten, audit, residency) | 23, 24, 18 |
| Inference serving judgment (when to self-host) | 12 |
| **Not closed here** (experience-gated per doc 01 §5/§8): real production traffic, on-call/incident response, org code-review, real-audit compliance, GPU economics at scale | — (requires a job/launched product) |

### Deliberate divergences from the prior Enterprise build

> After the revisions, the vector DB (Qdrant), orchestration (LangChain), and compute (EKS) now **match** the prior Enterprise. The remaining intentional divergences are:

| # | Layer | Prior Enterprise | Enterprise2 | Why diverge |
|---|---|---|---|---|
| 1 | Primary store | Postgres | **DynamoDB (single-table)** | NoSQL access-pattern modeling; KV scale; vectors fully delegated to Qdrant |
| 9 | Auth | Cognito | **Clerk** | Faster integration; learn a second auth provider |
| 11 | Queue | Celery | **ARQ + KEDA** | Async-native; learn beyond already-known Celery |
| 19 | A/B | (n/a) | **GrowthBook** | Adds an experimentation backbone you haven't used |
