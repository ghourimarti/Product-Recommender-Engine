# Phase 2 — Architecture Decision Log

> Status: **DRAFT / awaiting sign-off.** Context held constant for every decision: **NFRs from Phase 1** (1M MAU / 50k DAU / peak 500 concurrent / 300 RPS peak; first-token p95 ≤ 2s; 99.9% SLO; ≤ $0.004/req; ≤ $2,500/mo; GDPR-aware; us-east-1). **Team size = 1.** **Existing portfolio code** = Flask + AstraDB + Groq llama-3.1-8b + HF bge-base embeddings + LangChain LCEL + in-memory history.
>
> A recurring tension runs through this log: *"enterprise-grade demonstration"* vs *"one person can actually operate it on $2,500/mo."* Where they conflict, I optimize for **operational simplicity for a solo operator** unless the gap-closing/portfolio value justifies the extra burden — and I say so explicitly.

---

## Decision 1: Primary Database
**Question:** What stores users, conversations, messages, product/catalog metadata, feedback, and audit logs?
**Options considered:**
  - Option A — **PostgreSQL (RDS)**: mature relational DB. | Pros: ACID, JSON support, can also host pgvector (consolidation), huge ecosystem, you know SQL well. | Cons: needs connection pooling at scale. | Cost: RDS `db.t4g.medium` ~$60/mo, scales up. | Fits scale? **Y**
  - Option B — **DynamoDB**: managed NoSQL. | Pros: serverless, infinite scale, low ops. | Cons: rigid access patterns, no vector, no ad-hoc queries, painful for relational chat/audit data, you have only light exposure. | Cost: pay-per-request. | Fits scale? Y (but wrong shape)
  - Option C — **MongoDB Atlas**: document DB. | Pros: flexible schema, has vector search. | Cons: another vendor, weaker for relational/audit, you have light exposure. | Cost: ~$57/mo M10+. | Fits scale? Y
**Decision:** **PostgreSQL on RDS.**
**Reasoning:** Chat/users/audit data is relational; Postgres fits it natively. The decisive factor for a team of 1 is **consolidation** — Postgres can *also* be our vector store via pgvector (Decision 2), collapsing two systems into one to operate, back up, and secure. You already know SQL, so no learning tax. DynamoDB's access-pattern rigidity fights the ad-hoc querying we need for eval/audit.
**Trade-offs accepted:** Must add PgBouncer for connection pooling at peak RPS; vertical scaling has a ceiling we'd hit far beyond our target.
**Reversibility:** **Easy** for adding read replicas; **Moderate** to migrate off Postgres entirely. Revisit if write throughput exceeds a single primary (well past 300 RPS).

---

## Decision 2: Vector Database
**Question:** Where do product/review embeddings live for retrieval at 1–5M vectors with metadata filtering + hybrid search?
**Options considered:**
  - Option A — **pgvector (in our RDS Postgres)** *(new for you — 5-min primer: a Postgres extension adding a `vector` column type + HNSW/IVFFlat indexes; you query vectors with SQL `ORDER BY embedding <=> $1`).* | Pros: one system to run (huge for solo ops), transactional metadata+ACL+vector in one query, native hybrid (SQL `tsvector` BM25 + vector), no extra cost. | Cons: tops out around a few-to-~10M vectors before tuning pain; not purpose-built. | Cost: $0 beyond RDS. | Fits scale? **Y** at our 1–5M target.
  - Option B — **Qdrant** *(in your inventory)*: purpose-built vector DB. | Pros: fast filtered search, horizontal scale, great for >10M vectors, native hybrid. | Cons: another service to run/secure/back up; Qdrant Cloud adds cost. | Cost: self-host on a node, or Cloud ~$25–100+/mo. | Fits scale? **Y** (beyond our target too).
  - Option C — **AstraDB (current)** / **Pinecone**: managed serverless vector. | Pros: zero-ops vectors, already wired (AstraDB). | Cons: per-vendor cost + lock-in, data leaves your VPC (GDPR/compliance friction), separate system. | Cost: usage-based, can creep. | Fits scale? Y.
**Decision:** **Qdrant** (self-hosted on EKS for the build; Qdrant Cloud as managed alt). *[LOCKED — user override of the original pgvector default.]*
**Reasoning:** Purpose-built vector DB with native hybrid (dense + sparse) search, fast metadata-filtered retrieval, and horizontal-scaling headroom well past our 1–5M target — so it never becomes the bottleneck the way pgvector eventually would. It's in your course inventory, so no learning tax, and **"production Qdrant" is a stronger, more legible portfolio/CV signal than pgvector** — consistent with the same "prove enterprise capability" logic that chose EKS in D15. We migrate the current AstraDB usage to Qdrant. The retriever stays abstracted (Decision 6) so the store remains swappable.
**Trade-offs accepted:** Qdrant is a **separate stateful service** to run, secure, back up, and monitor (the operational simplification pgvector would have given is given up deliberately) — but this is the same kind of ops burden we already accepted with EKS, and it's gap-closing. Leaving AstraDB is a one-time migration.
**Reversibility:** **Moderate** — retriever abstraction means swapping Qdrant↔pgvector↔Pinecone is an adapter change + re-index, not an app rewrite. Revisit toward managed (Qdrant Cloud/Pinecone) if self-hosted Qdrant ops becomes a time sink.

---

## Decision 3: RAG vs Agentic vs Hybrid
**Question:** Which paradigm for the recommendation/Q&A core?
**Options considered:**
  - Option A — **Naive RAG (current)**: single dense retrieval → stuff → answer. | Pros: simplest, lowest latency/cost. | Cons: recall gaps, no query understanding, weak on comparative/multi-product queries. | Fits scale? Y but quality-limited.
  - Option B — **Advanced RAG (hybrid + rerank)**: dense+BM25 retrieval → reranker → context build → answer; history-aware query rewrite. | Pros: materially better recall/precision, handles "products like X for Y", citations. | Cons: +1 rerank hop (latency/cost), more moving parts. | Fits scale? **Y** within NFRs.
  - Option C — **Agentic RAG**: agent decides retrieval steps/tools. | Pros: handles complex multi-hop. | Cons: multiplies LLM calls (cost/latency), harder to keep under p95≤2s and $0.004/req, overkill for product Q&A. | Fits scale? N on cost/latency.
**Decision:** **Advanced RAG (hybrid retrieval + reranking + history-aware rewrite)**, non-agentic.
**Reasoning:** Product Q&A/recommendation is a retrieval-quality problem, not a planning problem. Hybrid+rerank directly fixes the demo's weak recall while staying inside the latency/cost NFRs. Agentic RAG's call multiplication would breach both p95≤2s and the $0.004/req ceiling for marginal benefit on this workload.
**Trade-offs accepted:** Rerank adds ~100–300ms and a model dependency; we forgo multi-hop reasoning (acceptable — out of scope).
**Reversibility:** **Easy** — retrieval is staged behind feature flags (dense → +hybrid → +rerank); agentic-RAG can be added later as a new path. Revisit if users need multi-hop/comparison-heavy reasoning.

---

## Decision 4: LLM Provider & Model Tiering
**Question:** Which model(s), and how do we tier for cost + survive provider outage?
**Options considered:**
  - Option A — **Single hosted model (current: Groq llama-3.1-8b)**. | Pros: simple, fast, cheap. | Cons: no quality escalation, single point of failure. | Cost: very low. | Fits scale? Y but fragile.
  - Option B — **Tiered hosted**: cheap default + escalate + cross-provider fallback. | Pros: cost-optimal, quality on demand, outage-resilient. | Cons: routing logic + multiple keys to manage. | Cost: low, controlled by routing. | Fits scale? **Y**
  - Option C — **Self-hosted (vLLM on GPU)**. | Pros: cost-flat at very high volume, data stays in VPC. | Cons: GPU ops + cost (~$500–1500/mo min), overkill below steady high volume. | Fits scale? Y but over budget for our pattern.
**Decision:** **Tiered hosted** — default **Groq `llama-3.1-8b-instant`**; escalate to **Groq `llama-3.3-70b`** (or `gpt-4o-mini`) on low retrieval confidence / long-complex queries; **fallback chain** Groq → OpenAI on outage.
**Reasoning:** Keeps the cheap, fast default you already use, adds quality only when retrieval confidence is low (cost-aware), and the cross-provider fallback is what buys the 99.9% SLO when one provider has an incident. Self-hosting can't be justified under $2,500/mo at our traffic shape.
**Trade-offs accepted:** Routing + confidence-scoring complexity; two provider accounts/keys to secure; some requests cost more when escalated.
**Reversibility:** **Easy** — provider/model behind a router interface; adding/removing a tier or provider is config. Revisit toward self-hosting only if steady volume makes API cost exceed GPU cost.

---

## Decision 5: Embedding Model
**Question:** Which embedding model, what dimensionality, multilingual, fine-tune?
**Options considered:**
  - Option A — **BAAI/bge-base-en-v1.5 (current)**, 768-dim, self-hosted. | Pros: strong quality/cost, no per-call API fee, data in-VPC, already used. | Cons: must run a small embedding service. | Cost: tiny CPU service. | Fits scale? **Y**
  - Option B — **OpenAI text-embedding-3-small** (1536-dim) / **-large** (3072). | Pros: zero-ops, high quality. | Cons: per-call cost on ingest of millions of vectors adds up, data leaves VPC, larger dims = bigger index. | Cost: $0.02/1M tokens (small). | Fits scale? Y.
  - Option C — **bge-large-en-v1.5** (1024-dim) self-hosted. | Pros: higher quality. | Cons: heavier, bigger index, marginal gain over base for this domain. | Fits scale? Y.
**Decision:** **bge-base-en-v1.5, 768-dim, self-hosted** behind a small embedding service; **text-embedding-3-small** as the managed fallback/alt.
**Reasoning:** Keeps cost near zero on bulk ingestion of millions of review vectors (the OpenAI per-call cost is the hidden killer at index-build time), keeps data in-VPC for GDPR, and 768-dim keeps the pgvector HNSW index lean for the ≤400ms NFR. English-only per scope → no multilingual model. No embedding fine-tuning v1 (not justified by ROI yet).
**Trade-offs accepted:** We operate a small embedding service (one more container); slightly lower ceiling than bge-large.
**Reversibility:** **Moderate** — changing embedding model = full re-index (the blue-green re-index path makes this safe but not instant). Revisit if retrieval quality eval demands a stronger model.

---

## Decision 6: Orchestration Framework
**Question:** What wires retrieval + prompt + LLM + memory together?
**Options considered:**
  - Option A — **LangChain LCEL (current)**. | Pros: already used, fast to build, rich integrations, history-aware retriever built in. | Cons: abstraction churn across versions, can obscure control flow. | Fits scale? Y.
  - Option B — **LlamaIndex**. | Pros: best-in-class ingestion/retrieval primitives. | Cons: another framework to learn, overlaps what LCEL already gives us here. | Fits scale? Y.
  - Option C — **Thin custom (no framework)**. | Pros: full control, no version churn, easiest to debug at scale. | Cons: we rebuild retrieval/memory plumbing. | Fits scale? Y.
  - Option D — **LangGraph**. | Pros: explicit state, needed for agentic. | Cons: overkill for non-agentic RAG. | Fits scale? Y but unnecessary.
**Decision:** **LangChain LCEL retained, but wrapped behind our own thin `Retriever`/`Generator` interfaces.**
**Reasoning:** Minimizes churn from the existing code (you built it on LCEL) while the thin wrapper buys us framework-independence — if LangChain breaks or we want to drop it, we change adapters, not the app. This directly addresses the build-spec principle of avoiding framework lock-in. LangGraph is deferred to the day we add agentic-RAG (Decision 3 reversibility).
**Trade-offs accepted:** A small abstraction layer to maintain; we don't get LlamaIndex's fancier retrievers out of the box.
**Reversibility:** **Easy** — that's the entire point of the wrapper.

---

## Decision 7: Backend Language & Framework
**Question:** What serves the API?
**Options considered:**
  - Option A — **FastAPI (Python)**. | Pros: async, native SSE streaming, Pydantic schemas, same language as the AI stack (no context-switch), huge ecosystem. | Cons: Python concurrency needs care (workers). | Fits scale? **Y**
  - Option B — **Flask (current)**. | Pros: already here, simple. | Cons: sync by default, clumsy streaming, no native async — wrong tool for streaming LLM at concurrency. | Fits scale? Weak.
  - Option C — **Node (NestJS)** / **Go**. | Pros: excellent concurrency. | Cons: splits the codebase from the Python AI core, re-implements LLM glue, you'd carry two ecosystems. | Fits scale? Y but costly for a solo dev.
**Decision:** **FastAPI (Python), async, REST + SSE.**
**Reasoning:** The AI stack is Python; keeping the backend Python means one language, one set of skills, shared models/code with the RAG core — decisive for a team of 1. FastAPI's native async + SSE is exactly what token streaming under concurrency needs, which Flask handles poorly. We migrate off Flask.
**Trade-offs accepted:** Must run multiple Uvicorn workers + manage Python GIL implications (mitigated: work is I/O-bound on LLM calls, where async shines).
**Reversibility:** **Moderate** — it's a rewrite of the web layer (but the demo's web layer is tiny). Done early so cost is low now.

---

## Decision 8: Frontend Framework & Streaming UX
**Question:** What does the user-facing app look like, and how does streaming/cancel/retry work?
**Options considered:**
  - Option A — **Next.js (App Router)**. | Pros: industry-standard, SSR/edge, great streaming support, strong portfolio signal, easy auth integration. | Cons: heavier than needed for a chat UI. | Fits scale? **Y**
  - Option B — **Vite + React SPA**. | Pros: lighter, simpler, static-hostable on S3+CloudFront (cheap). | Cons: less batteries-included (routing/SSR/auth). | Fits scale? Y.
  - Option C — **Keep jQuery/Bootstrap (current)** / **Streamlit**. | Pros: trivial. | Cons: no real streaming UX, not a credible production/portfolio frontend. | Fits scale? N as a product.
**Decision:** **Next.js (App Router) + Tailwind + shadcn/ui**, with **Vite+React SPA** as the documented lighter alt.
**Reasoning:** This is a portfolio asset as much as a product; Next.js is the expected, employable choice and handles SSE token streaming, cancellation (AbortController), and retry cleanly. The current jQuery UI isn't a credible production frontend. **Streaming UX:** SSE token stream, stop button (abort), retry-on-error, optimistic user-echo, citations rendered inline as the answer streams.
**Trade-offs accepted:** More build weight than a recommender strictly needs; a small hosting cost (or Vercel/Amplify).
**Reversibility:** **Easy** — frontend is decoupled via the API; swap freely.

---

## Decision 9: Authentication & Authorization
**Question:** How do users authenticate; how is data isolated; multi-tenant?
**Options considered:**
  - Option A — **AWS Cognito**. | Pros: AWS-native, JWT, integrates with our stack, cheaper-than-Clerk at scale. | Cons: clunky DX; **per-MAU cost still ~$0.0055 → ~$5.5k/mo at 1M MAU (over budget alone!)**. | Fits scale? Partial (cost cliff).
  - Option B — **Clerk**. | Pros: best DX, fastest to integrate for solo dev. | Cons: per-MAU pricing is **prohibitive at 1M MAU** (tens of $k/mo). | Fits scale? **N on cost.**
  - Option C — **Self-hosted (Ory Kratos / Supabase GoTrue)**. | Pros: cheap at any scale, data in-VPC. | Cons: real ops burden for a solo dev. | Fits scale? Y on cost, heavy on ops.
**Decision:** **AWS Cognito + a provider-agnostic JWT/OIDC verification interface from day one.** *[LOCKED — user delegated; Keycloak-on-EKS offered as the opt-in harder path.]* AuthZ = **JWT + RBAC + per-user row-level data isolation**; **single-tenant**.
**Reasoning:** Auth carries an **asymmetric downside the other layers don't**: EKS's worst case is "cluster down" (recoverable, and the exact gap we're closing); self-hosted auth's worst case is "every user's credentials leaked" (catastrophic, irreversible, real client liability). The cardinal auth rule — *don't operate more security surface than you must* — overrides the portfolio-signal logic that won EKS in D15. The per-MAU cost cliff is **real but theoretical** for a portfolio piece (never 1M *real* MAU), and the day-one abstraction makes the IdP a swappable dependency, so migrating to self-hosted auth at true scale is config + user-migration, not a rewrite. Cognito is AWS-native (matches D14), low-ops, and an employable skill.
**Trade-offs accepted:** Cognito DX friction; a documented cost cliff requiring IdP migration at very high MAU; we forgo the (legitimate but heavier) Keycloak-on-EKS portfolio story.
**Reversibility:** **Moderate** — JWT verification is abstracted from day one; swapping to Keycloak/Ory/GoTrue is an IdP change behind the same interface, with user migration as the real work. Revisit trigger: MAU auth-cost approaching ~10% of budget, or a client requiring fully in-VPC identity.

---

## Decision 10: Caching Strategy
**Question:** What do we cache to hit cost + latency NFRs?
**Options considered:**
  - Option A — **Redis (ElastiCache)**: response + semantic + embedding cache. | Pros: one cache for all layers, fast, supports vector for semantic cache. | Cons: a service to run; cache-invalidation discipline. | Cost: ~$15–50/mo. | Fits scale? **Y**
  - Option B — **Memcached**. | Pros: simple, fast. | Cons: no native structures for semantic cache. | Fits scale? Y but limited.
  - Option C — **No cache / CDN-only**. | Pros: simplest. | Cons: blows the $0.004/req and latency budgets under load. | Fits scale? N.
**Decision:** **Redis (ElastiCache)** with three layers: **response cache** (exact-match), **semantic cache** (embed query → return cached answer on high similarity), **embedding cache** (avoid re-embedding repeat queries).
**Reasoning:** Semantic cache is the single biggest lever on both cost ($0.004/req) and latency at scale — common product questions repeat heavily. Redis does all three layers in one system. **Invalidation:** TTL + a catalog-version key bumped on re-index so stale answers expire when the catalog changes.
**Trade-offs accepted:** Cache-invalidation correctness is on us; semantic cache can occasionally serve a "close enough" answer (mitigated by a tight similarity threshold + TTL).
**Reversibility:** **Easy** — caching is a wrapper around the RAG call.

---

## Decision 11: Queue & Async Work
**Question:** What handles ingestion/re-index and any async jobs?
**Options considered:**
  - Option A — **ARQ (async Redis queue)**. | Pros: async-native (fits FastAPI), reuses our Redis, far simpler than Celery for a solo dev. | Cons: smaller ecosystem than Celery. | Fits scale? **Y** (ingestion is not request-path).
  - Option B — **Celery + Redis (build-spec default)**. | Pros: battle-tested, feature-rich. | Cons: heavier, sync-oriented, more config for one worker type. | Fits scale? Y.
  - Option C — **SQS + worker**. | Pros: AWS-native, durable, decoupled. | Cons: another service, more plumbing than needed for ingestion-only. | Fits scale? Y.
**Decision:** **ARQ** for ingestion/re-index; **SQS** noted as the AWS-native alt if we later need durable cross-service decoupling.
**Reasoning:** The only async work in v1 is catalog ingestion/re-index — *not* on the request path. ARQ reuses Redis (no new system), is async-native with FastAPI, and is the lightest thing that works for a solo operator. Celery's weight isn't justified for one job type.
**Trade-offs accepted:** ARQ's smaller community; if we grow many heterogeneous job types we'd reconsider Celery/SQS.
**Reversibility:** **Easy** — jobs are defined behind a task interface.

---

## Decision 12: Inference Serving
**Question:** How are the LLM and embedding model served?
**Options considered:**
  - Option A — **LLM via provider API; embeddings via small self-hosted bge service**. | Pros: no GPU ops/cost for LLM, embeddings cheap on CPU, data-in-VPC for embeddings. | Cons: provider dependency (mitigated by Decision 4 fallback). | Cost: low. | Fits scale? **Y**
  - Option B — **Self-host LLM (vLLM/TGI on GPU)**. | Pros: flat cost at high steady volume, full control. | Cons: GPU $/ops over budget for our pattern. | Fits scale? Y but over budget.
  - Option C — **SageMaker / Bedrock endpoints**. | Pros: managed. | Cons: cost + less flexible model choice than Groq for our cheap-default. | Fits scale? Y.
**Decision:** **Provider API for the LLM (Groq/OpenAI per Decision 4); self-hosted bge embedding microservice (CPU).**
**Reasoning:** bge-base runs fine on CPU, so a small embedding container is cheap and keeps ingestion cost ~$0 and data in-VPC; the LLM stays on hosted APIs because GPU self-hosting can't be justified under budget at our traffic. Bedrock is the documented path if a client demands everything in-VPC.
**Trade-offs accepted:** LLM provider dependency (covered by fallback chain); we run + scale the embedding service.
**Reversibility:** **Easy** for LLM (router). **Moderate** for embeddings (tied to Decision 5 re-index).

---

## Decision 13: Observability Stack
**Question:** What do we log/trace/meter, and where?
**Options considered:**
  - Option A — **OpenTelemetry → Prometheus/Grafana (extend existing) + Langfuse for LLM**. | Pros: builds on the Prometheus/Grafana already in the repo, OTel is vendor-neutral, Langfuse is purpose-built for LLM traces/cost/eval and self-hostable (GDPR). | Cons: a few systems to run. | Cost: low (self-host) or Grafana Cloud free tier. | Fits scale? **Y**
  - Option B — **Datadog**. | Pros: one pane of glass. | Cons: cost balloons at scale, no LLM-native depth. | Fits scale? Y but pricey.
  - Option C — **CloudWatch only**. | Pros: AWS-native, simplest. | Cons: weak tracing, no LLM observability. | Fits scale? Partial.
**Decision:** **OTel → Prometheus + Grafana** (extend the repo's existing monitoring; **Grafana Cloud** free/cheap tier as managed alt) for app; **Langfuse** (self-hosted) for LLM tracing, token/cost, prompt versions, eval-in-prod.
**Reasoning:** Reuses what's already in the repo (Prometheus/Grafana), keeps the LLM-specific layer (the actual gap from your skill audit) on Langfuse which is open-source and self-hostable to satisfy GDPR. **We trace:** request→retrieval→rerank→generation spans, token/cost per request, cache hit-rate, retrieval vs generation latency split. **We alert on:** SLO burn, p99 latency, error rate, cost-per-hour, cache hit-rate drop.
**Trade-offs accepted:** Operating Langfuse + Grafana stack (mitigated by managed tiers if ops gets heavy).
**Reversibility:** **Easy** — OTel means we can repoint to any backend.

---

## Decision 14: Cloud Provider & Core Services
**Question:** Which cloud and which managed services?
**Options considered:**
  - Option A — **AWS**. | Pros: your background, broadest service set, RDS/ElastiCache/EKS/S3/Bedrock all present. | Cons: complexity, easy to overspend. | Fits scale? **Y**
  - Option B — **GCP**. | Pros: great K8s (GKE), strong data. | Cons: less aligned with your AWS skills. | Fits scale? Y.
  - Option C — **Azure**. | Pros: Azure OpenAI. | Cons: least aligned with your stack here. | Fits scale? Y.
**Decision:** **AWS.** Core services: **VPC** (networking), **EKS** (compute, Decision 15), **RDS Postgres+pgvector** (data), **ElastiCache Redis** (cache/queue), **S3** (raw catalog + artifacts), **ALB + ACM** (ingress/TLS), **Secrets Manager + KMS** (secrets), **ECR** (images), **CloudWatch** (infra metrics/logs), **CloudFront** (static + cacheable responses).
**Reasoning:** AWS-first per your background and the build-spec; every service we need has a first-party managed option, minimizing solo ops.
**Trade-offs accepted:** AWS cost vigilance required (Decision 20).
**Reversibility:** **Hard** to fully re-cloud, but Terraform + containers keep workloads portable. Not expected to revisit.

---

## Decision 15: Container, Orchestration & IaC
**Question:** How is it packaged, orchestrated, and provisioned?
**Options considered:**
  - Option A — **EKS (managed K8s) + Helm + Terraform**. | Pros: closes the production-Kubernetes gap from your audit, strongest portfolio signal, HPA/PDB/probes. | Cons: control-plane $73/mo + node cost + real ops complexity for a solo dev. | Fits scale? **Y**
  - Option B — **ECS Fargate + Terraform**. | Pros: far simpler/cheaper to operate solo, serverless containers. | Cons: doesn't demonstrate K8s (your stated gap), less portable. | Fits scale? Y.
  - Option C — **Fly.io / Cloud Run**. | Pros: simplest, cheap. | Cons: not the enterprise target, weak portfolio signal for this goal. | Fits scale? Y for many cases.
**Decision:** **EKS + Helm + Terraform**; **ECS Fargate documented as the simpler/cheaper alternative**. Docker: multi-stage, slim base, non-root, pinned deps, weights-from-S3 (not baked). Local: **kind/minikube**. IaC module structure: `network / data / cache / eks / app / observability`, remote state in S3 + DynamoDB lock, per-env workspaces.
**Reasoning:** This is the decision where I deliberately accept **more ops burden than a solo operator strictly needs**, because **"production Kubernetes" is explicitly one of the biggest gaps in your skill audit** and the highest-value thing this portfolio piece can prove. The build value outweighs the simplicity ECS would give. I'm flagging the trade honestly: if your goal were purely "ship cheapest," ECS wins; because your goal is "prove enterprise K8s capability," EKS wins.
**Trade-offs accepted:** EKS control-plane cost + steeper operations; you'll spend real time on K8s debugging (which is the point).
**Reversibility:** **Moderate** — containers run on ECS too; Helm→ECS task defs is a deployment-layer change, not an app change.

---

## Decision 16: CI/CD Pipeline Shape
**Question:** How does code/model/prompt get to prod safely?
**Options considered:**
  - Option A — **GitHub Actions**. | Pros: free for public/portfolio, ubiquitous, you know it. | Cons: self-hosted runners if heavy. | Fits scale? **Y**
  - Option B — **GitLab CI / Jenkins / CircleCI** (all in your inventory). | Pros: powerful. | Cons: more to host/maintain than GH Actions for a solo dev. | Fits scale? Y.
**Decision:** **GitHub Actions.** Stages: **lint → unit → integration → RAGAS eval gate → build+push ECR → deploy dev → manual gate → staging (load test) → prod**. Environments: **dev / staging / prod**. Promotion: **image-digest** promotion. Rollback: **Helm rollback** + previous digest.
**Reasoning:** Lowest-friction, free for a portfolio repo, and you already know it. The distinctive part is the **RAGAS eval gate** — prompt/retrieval regressions fail the build, which is the production-grade behavior most demos lack.
**Trade-offs accepted:** GH-hosted runner limits (fine at our scale).
**Reversibility:** **Easy.**

---

## Decision 17: Secrets & Configuration Management
**Question:** Where do secrets live, how do they rotate, how does config differ per env?
**Options considered:**
  - Option A — **AWS Secrets Manager + External Secrets Operator (ESO) → K8s**; config via `pydantic-settings` + ConfigMaps. | Pros: AWS-native, rotation support, secrets never in git/images, ESO syncs to pods. | Cons: ESO is one more operator. | Fits scale? **Y**
  - Option B — **SSM Parameter Store**. | Pros: cheaper than Secrets Manager. | Cons: weaker rotation story. | Fits scale? Y.
  - Option C — **Sealed Secrets / .env (current)**. | Pros: simple. | Cons: `.env` is not production-grade; secrets risk. | Fits scale? N.
**Decision:** **Secrets Manager + External Secrets Operator + KMS**; config via `pydantic-settings`, per-env via ConfigMaps/workspaces; **SSM Parameter Store** as the cheaper alt for non-rotating config.
**Reasoning:** Removes the current `.env`-in-repo risk, gives real rotation, and ESO is the clean K8s-native way to surface AWS secrets to pods. This closes the secrets-management gap from your audit.
**Trade-offs accepted:** ESO operator to run; Secrets Manager per-secret cost (negligible at our count).
**Reversibility:** **Easy** — config layer is abstracted.

---

## Decision 18: Security Posture
**Question:** What's the threat model and which mitigations?
**Threats:** prompt injection **via product reviews** (reviews are untrusted user-generated content — the #1 risk here: a malicious review could carry "ignore instructions" text into the context), jailbreaks, PII leakage in logs, data exfiltration, output abuse, credential/secret exposure, DDoS/abuse.
**Options considered:** (defense-in-depth vs minimal guardrails vs WAF-only) — chosen: layered.
**Decision:** **Defense-in-depth:** (1) **treat retrieved review text as data, not instructions** — wrap/escape retrieved content, system prompt hardening, never let context override instructions; (2) input + output **guardrails** (moderation + injection classifier, e.g., Llama Guard / regex+LLM); (3) **PII scrubbing in logs** + no payload logging by default; (4) **rate limiting + per-user quotas** (Decision 20) + **AWS WAF** on the ALB; (5) **least-privilege IAM** + secrets via Decision 17; (6) **per-user row-level data isolation** (Decision 9); (7) **audit log** of queries + admin actions.
**Reasoning:** Untrusted UGC in the retrieval corpus makes prompt-injection-via-context the dominant, often-overlooked threat for *this* app specifically (your data poisoning coursework applies directly). The rest is standard production hardening that closes the security gaps from your audit.
**Trade-offs accepted:** Guardrail calls add minor latency/cost; some false-positive moderation.
**Reversibility:** **Easy** to tune; **Moderate** to add heavier controls (e.g., full DLP).

---

## Decision 19: Evaluation Strategy
**Question:** How do we measure quality and catch regressions?
**Options considered:** (RAGAS offline gate vs LLM-judge only vs manual) — chosen: layered.
**Decision:** **Offline golden Q/A dataset + RAGAS** (faithfulness, answer-relevancy, context-precision/recall) as a **CI gate**; **online eval sampling** + **thumbs-up/down feedback** capture; **A/B testing** of prompts/models via Langfuse.
**Reasoning:** This is the highest-ROI gap-closer from your audit. The offline RAGAS gate makes prompt/retrieval changes safe; online sampling + feedback catches what offline misses; Langfuse A/B lets you prove a change before full rollout. Eval is the layer that most separates "production" from "demo."
**Trade-offs accepted:** Building/maintaining the golden set; judge-model cost on eval runs (sampled).
**Reversibility:** **Easy** — additive.

---

## Decision 20: Cost Controls
**Question:** How do we guarantee ≤ $0.004/req and ≤ $2,500/mo?
**Decision:** **Per-user + per-IP rate limiting**; **per-user/day token budgets**; **semantic+response cache** (biggest lever, Decision 10); **cheap-model default + tiering** (Decision 4); **spend monitoring** (Langfuse token-cost + CloudWatch infra-cost) with **alerts at 50/80/100% of budget**; **kill-switch** env flag to force cheapest model / shed load; **GPU-free architecture** (Decision 12) to avoid the biggest cost line.
**Reasoning:** Cost is an SLO here, not an afterthought. Cache + cheap-default do most of the work; budgets + kill-switch are the backstop that prevents a runaway bill (the failure mode that kills solo-operated products).
**Trade-offs accepted:** Rate limits/budgets can throttle legitimate heavy users (tunable).
**Reversibility:** **Easy.**

---

## Decision 21: Failure-Mode & Degradation Strategy
**Question:** What happens when each dependency fails?
**Decision (explicit fallback table):**
  - **LLM provider down** → fallback provider (Decision 4) → if all down, serve cached/"can't answer right now" with retrieved products listed (graceful, not blank).
  - **Vector DB slow/down** → timeout → degrade to keyword/BM25-only or cached results → honest partial answer.
  - **Retrieval returns nothing** → don't hallucinate; return "no matching products found" + suggest broadening.
  - **Rerank service down** → skip rerank, serve dense results (feature-flag bypass).
  - **Embedding service down** → serve from response/embedding cache; queue re-embeds.
  - **Redis down** → bypass cache, hit source directly (slower, still correct) with circuit breaker.
  - **Malicious input** → guardrail reject with safe message (Decision 18).
  - Cross-cutting: **retries with exponential backoff + jitter, circuit breakers, timeouts on every external call.**
**Reasoning:** 99.9% SLO is impossible without explicit per-dependency degradation; the principle is *degrade, don't fail* — always return something useful and honest.
**Trade-offs accepted:** Degraded modes give lower-quality answers (acceptable vs downtime).
**Reversibility:** **Easy** — additive resilience.

---

## Decision 22: Repo Structure & Code Organization
**Question:** Monorepo or polyrepo; where do prompts/evals/infra live?
**Options considered:** (monorepo vs polyrepo) — chosen: monorepo.
**Decision:** **Monorepo.** Top-level: `frontend/` (Next.js), `backend/` (FastAPI: `app/{api,rag,core,observability,schemas,workers}`, `tests/{unit,integration,evaluation}`), `embedding-service/`, `infra/{terraform,helm,monitoring}`, `eval/` (golden dataset + RAGAS runner), `load_tests/` (k6), `.github/workflows/`, `docker-compose.yml`. **Prompts** live in `backend/app/rag/prompts/` (versioned in git) + Langfuse for runtime versioning. **Evals** in `eval/`. **Infra** in `infra/`.
**Reasoning:** A solo dev moves fastest with one repo, atomic cross-cutting changes, and one CI. Polyrepo's isolation isn't worth the coordination overhead at team-size-1. This mirrors the `extras/P1-Enterprise` reference layout so patterns carry across your portfolio.
**Trade-offs accepted:** Monorepo CI must be path-filtered to avoid rebuilding everything on every change.
**Reversibility:** **Moderate** — splitting later is mechanical.

---

## Decisions flagged for your explicit attention
1. **D2 pgvector vs Qdrant** — I chose pgvector for solo-ops simplicity (Qdrant is in your inventory and is the documented escape hatch). Push back if you'd rather build on Qdrant to showcase a purpose-built vector DB.
2. **D9 Auth cost cliff** — Cognito is fine for the build but per-MAU pricing breaks the budget at literal 1M MAU; real scale needs self-hosted auth. Accept Cognito-for-now, or build self-hosted from the start?
3. **D15 EKS vs ECS** — I chose EKS deliberately to close your Kubernetes gap, accepting more ops/cost than ECS. If you'd rather optimize for simplicity/cost over proving K8s, we switch to ECS Fargate.
4. **D8 Next.js vs Vite SPA** — Next.js for portfolio signal; Vite SPA is lighter/cheaper. Either is fine.
