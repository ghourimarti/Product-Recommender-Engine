# Production-Grade RAG Product Recommender — Case Study

> Portfolio asset for Upwork / LinkedIn / case-study page. Numbers marked **(target)** are
> Phase-1 design NFRs; replace **(measure)** cells with real figures after the staging load test
> (Phase 6, rung 5). Do not quote targets as if measured.

## The problem
A product-review chatbot existed as a portfolio demo: a single-file Flask app, one shared
in-memory chat session (every user saw the same history), AstraDB + Groq wired directly into
the request path, no tests, no auth, no caching, no observability, no deployment beyond a
single container. It "worked on my machine" but could not be operated for real users.

**Goal:** transform it, in place and layer by layer, into a production-grade system that could
serve a large user base — without rewriting from scratch.

## What I built
An end-to-end RAG application with a clean, swappable architecture:

- **Retrieval:** Qdrant vector store with **hybrid (dense + BM25) search + cross-encoder
  reranking**; self-hosted bge embeddings (data stays in-VPC).
- **Generation:** tiered LLMs (cheap default, escalate on complex queries) with **cross-provider
  fallback** for outage resilience.
- **API:** async FastAPI with **SSE token streaming**, per-user isolated chat history
  (Postgres), and Pydantic contracts.
- **Platform:** Redis response + **semantic cache**, Cognito/JWT auth (provider-agnostic),
  rate limiting + per-user token budgets + kill-switch, prompt-injection + PII defenses,
  retry/circuit-breaker degradation.
- **Ops:** Prometheus + OpenTelemetry + **Langfuse** (token/cost tracing), Dockerized stack,
  **EKS + Helm**, **Terraform** (VPC/EKS/RDS/ElastiCache/ECR/Secrets), GitHub Actions CI/CD with
  a **RAGAS quality gate** and Trivy image scanning, k6 load tests.

## Architecture
See [`architecture.md`](architecture.md) for the component diagram and request flow.
Frontend (Next.js, streaming) → FastAPI (auth → rate/budget → guardrails → RagService) →
cache → tiered LLM engine → hybrid retriever + reranker → Qdrant + embedding service;
Postgres for history/audit; OTel+Langfuse for observability.

## Key decisions and trade-offs (from the 22-entry Decision Log)
| Decision | Choice | Trade-off accepted |
|---|---|---|
| Vector DB | **Qdrant** (over pgvector) | extra stateful service to operate, for headroom + a stronger CV signal |
| RAG paradigm | **Advanced (hybrid + rerank)**, not agentic | +1 rerank hop of latency; rejected agentic's call-multiplication on cost |
| LLM strategy | **tiered + cross-provider fallback** | routing complexity, for cost control + 99.9% SLO under provider outage |
| Auth | **Cognito + day-one abstraction** | per-MAU cost cliff at true scale (documented), for low solo-ops + no auth liability |
| Compute | **EKS** (over ECS) | more ops/cost, deliberately, to demonstrate production Kubernetes |
| Caching | **semantic cache** | rare "close-enough" answers (tight threshold + TTL), for the biggest cost lever |

## Scale & performance
| Metric | Target | Measured (staging) |
|---|---|---|
| First-token p95 | < 2.0s | (measure) |
| Full-answer p95 | < 6s | (measure) |
| Recommend/search p95 | < 400ms | (measure) |
| Throughput | 100 RPS sustained, 300 RPS peak | (measure) |
| Error rate (SLO) | < 1% (99.9%) | (measure) |
| Cache hit-rate | — | (measure) |

## Cost
| Metric | Target | Measured |
|---|---|---|
| Cost / request (blended w/ cache) | ≤ $0.004 | (measure) |
| Monthly infra + LLM @ scale | ≤ $2,500 | (measure) |

Cost levers in place: semantic cache (largest), cheap-default model tiering, self-hosted
embeddings (no per-call fee on bulk ingest), per-user budgets + kill-switch, GPU-free design.

## Engineering practices demonstrated
- **24 reviewable commits**, each ending in a working, tested system (one transformation step
  per commit, tagged to its Decision Log entry).
- **54 automated tests** (unit + integration), CI-gated; **RAGAS** quality gate blocks prompt/
  retrieval regressions; bandit SAST + Trivy image scan; pip-audit + license audit.
- **Degrade-don't-fail**: every external dependency has timeout + retry; Redis/LLM/vector-DB
  outages degrade gracefully (proven by tests).
- **GDPR**: right-to-be-forgotten deletion path; PII-scrubbed logs; in-VPC embeddings.

## What I'd do differently next time
- Capture **real LLM token usage** from provider metadata at the start (I estimated tokens
  for budgeting; metadata-based accounting is more accurate).
- Introduce a **lockfile (uv/pip-tools)** from day one rather than `~=` pins — the langchain
  ecosystem's version churn cost time.
- Stand up the **eval harness even earlier** and treat the golden set as a living artifact —
  it's the single highest-leverage thing for shipping RAG safely.
- For true multi-tenant scale, move auth to **self-hosted (Keycloak/Ory)** before the Cognito
  per-MAU cost cliff bites.

## Honest scope boundary
This system is **built and architected** for scale and **validated under synthetic load**; it has
not yet served millions of real users in production. The architecture, tests, IaC, and runbooks
are production-grade; the remaining gap — sustained real traffic, on-call incident history, and
operating inside an engineering org — is acquired by running it live, not by building it. That
boundary is stated plainly because clients can tell the difference.
