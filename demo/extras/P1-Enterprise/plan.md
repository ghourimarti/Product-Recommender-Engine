# P1 Anime Recommender Enterprise — Project Plan

## What This Project Is

An enterprise-grade rebuild of the original bootcamp anime recommender (P1-Video-SEO-Engine).
The v1 project was a working RAG chatbot built by following a course. This v2 project
demonstrates the same core idea but built to enterprise standards — with auth, security,
observability, evaluation, load testing, and production-grade Kubernetes deployment.

**The primary purpose of this project is to fill specific portfolio gaps identified in a
course coverage analysis.** Each added layer maps to a real gap.

---

## Gap Coverage Map

| Gap Identified | What Was Added | File |
|---|---|---|
| Deprecated `RetrievalQA` / `langchain_classic` | LCEL chain (`RunnablePassthrough` + `ChatPromptTemplate`) | `backend/app/rag/pipeline.py` |
| No production API layer | FastAPI with SSE streaming, Pydantic schemas, versioned routes | `backend/app/main.py`, `api/routes/` |
| No auth | JWT (HS256) + bcrypt password hashing | `backend/app/core/security.py` |
| No rate limiting | SlowAPI per-IP limiter (10 req/min) | `backend/app/core/rate_limiter.py` |
| No LLM security | 13 prompt injection regex patterns + PII detector (email, phone, SSN, card) | `backend/app/core/guardrails.py` |
| No output validation | Output length + emptiness guard | `backend/app/core/guardrails.py` |
| No metrics | 8 Prometheus metrics (requests, latency, tokens, cost, guardrail violations, active streams) | `backend/app/observability/metrics.py` |
| No structured logging | loguru JSON logs with rotation/retention | `backend/app/observability/logger.py` |
| No cost tracking | Character-based token estimation + USD cost per request | `backend/app/observability/cost_tracker.py` |
| No RAG evaluation | RAGAS (faithfulness + answer_relevancy) + 20 golden Q&A pairs | `backend/tests/evaluation/` |
| No evaluation CI | GitHub Actions workflow triggered on RAG code changes in PRs | `.github/workflows/rag-eval.yml` |
| No unit tests | 30+ unit tests across guardrails, security, cost tracker | `backend/tests/unit/` |
| No integration tests | Full API endpoint tests with mocked RAG chain | `backend/tests/integration/` |
| No streaming | Server-Sent Events (SSE) via FastAPI `StreamingResponse` | `backend/app/api/routes/recommend.py` |
| No RBAC | Admin vs user roles, admin-only cost/usage endpoints | `backend/app/api/routes/admin.py` |
| No load testing | k6 script: ramp 0→20 VU, p95 < 15s threshold | `load_tests/k6_script.js` |
| Basic Kubernetes | HPA (min 2, max 10), liveness/readiness probes, resource limits, PVC | `infra/k8s/` |
| No network isolation | Kubernetes NetworkPolicy (frontend→backend only, Prometheus allowed) | `infra/k8s/network-policy.yaml` |
| No CI pipeline | GitHub Actions: ruff lint + mypy + unit + integration + Docker build/push | `.github/workflows/ci.yml` |
| No Grafana dashboard | 8-panel dashboard auto-provisioned (request rate, latency p50/p95/p99, tokens, cost, violations) | `infra/monitoring/dashboards/` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        docker-compose                        │
│                                                             │
│  ┌──────────────┐    JWT + SSE     ┌──────────────────────┐ │
│  │  Streamlit   │ ──────────────▶  │     FastAPI           │ │
│  │  Frontend    │                  │                       │ │
│  │  :8501       │                  │  /v1/auth/token       │ │
│  └──────────────┘                  │  /v1/recommend (SSE)  │ │
│                                    │  /v1/admin/usage      │ │
│                                    │  /health  /ready      │ │
│                                    │  /metrics             │ │
│                                    │  :8000                │ │
│                                    └──────────┬───────────┘ │
│                                               │             │
│                              ┌────────────────┼──────────┐  │
│                              │   RAG Pipeline (LCEL)     │  │
│                              │                           │  │
│                              │  ChromaDB ──▶ Retriever   │  │
│                              │  HuggingFace Embeddings   │  │
│                              │  Groq LLM (streaming)     │  │
│                              └───────────────────────────┘  │
│                                                             │
│  ┌──────────────┐  scrape /metrics  ┌──────────────────┐   │
│  │  Prometheus  │ ◀──────────────── │   FastAPI        │   │
│  │  :9090       │                   │   /metrics       │   │
│  └──────┬───────┘                   └──────────────────┘   │
│         │ datasource                                        │
│  ┌──────▼───────┐                                          │
│  │   Grafana    │                                          │
│  │   :3000      │  8 panels: req rate, latency, tokens,    │
│  └──────────────┘  cost, violations, active streams        │
└─────────────────────────────────────────────────────────────┘
```

### Request Lifecycle

```
User query
    │
    ▼
[Streamlit] POST /v1/recommend  +  Bearer <JWT>
    │
    ▼
[FastAPI] JWT verification  →  401 if invalid/expired
    │
    ▼
[SlowAPI] Rate limit check  →  429 if > 10 req/min
    │
    ▼
[Guardrails] Input validation:
    - Length check (3–500 chars)
    - Prompt injection detection (13 regex patterns)
    - PII detection (email, phone, SSN, credit card)
    →  422 if blocked, reason returned to user
    │
    ▼
[RAG Pipeline — LCEL]
    - ChromaDB similarity search (k=5 docs)  →  timed → Prometheus histogram
    - ChatPromptTemplate (system + human)
    - ChatGroq streaming (llama-3.1-8b-instant)
    - StrOutputParser
    │
    ▼
[SSE Stream] chunks yielded to client in real time
    │
    ▼
[Output Guardrail] emptiness + minimum length check
    │
    ▼
[Cost Tracker] estimate input/output tokens → log cost → Prometheus counters
    │
    ▼
Stream ends: [DONE] signal + __cost__<usd> metadata sent to client
```

---

## File Structure

```
P1-Anime-Recommender-Enterprise/
│
├── backend/
│   ├── app/
│   │   ├── main.py                      FastAPI app, middleware, metric endpoint
│   │   ├── api/routes/
│   │   │   ├── auth.py                  POST /v1/auth/token
│   │   │   ├── recommend.py             POST /v1/recommend  (SSE streaming)
│   │   │   ├── health.py                GET /health  GET /ready
│   │   │   └── admin.py                 GET /v1/admin/usage  /cost  (admin only)
│   │   ├── core/
│   │   │   ├── config.py                Pydantic Settings from .env
│   │   │   ├── security.py              JWT sign/verify, bcrypt, USERS_DB
│   │   │   ├── rate_limiter.py          SlowAPI limiter singleton
│   │   │   └── guardrails.py            Input + output validation
│   │   ├── rag/
│   │   │   ├── pipeline.py              LCEL chain, streaming, timed retrieval
│   │   │   ├── vector_store.py          ChromaDB build + load
│   │   │   └── prompt.py                System + human prompt templates
│   │   ├── observability/
│   │   │   ├── metrics.py               8 Prometheus metrics
│   │   │   ├── logger.py                loguru structured JSON logger
│   │   │   └── cost_tracker.py          Token estimation + USD tracking
│   │   └── schemas/
│   │       ├── request.py               AuthRequest, RecommendRequest
│   │       └── response.py              TokenResponse, HealthResponse, etc.
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_guardrails.py       30 cases: valid, injection, PII, length
│   │   │   ├── test_security.py         JWT creation, expiry, auth logic
│   │   │   └── test_cost_tracker.py     Token estimation, cost accumulation
│   │   ├── integration/
│   │   │   └── test_api_endpoints.py    Full API tests with mocked RAG chain
│   │   └── evaluation/
│   │       ├── golden_dataset.json      20 Q&A pairs for RAGAS evaluation
│   │       └── eval_ragas.py            RAGAS runner, exits 1 if below threshold
│   │
│   ├── conftest.py                      Sets env vars before app import
│   ├── pyproject.toml                   pytest config + ruff + mypy settings
│   ├── requirements.txt                 Pinned dependencies
│   └── Dockerfile                       Multi-stage build
│
├── frontend/
│   ├── app.py                           Streamlit: login gate, SSE consumer, cost display
│   └── Dockerfile
│
├── load_tests/
│   └── k6_script.js                     Ramp 0→20 VU, p95<15s, error rate<5%
│
├── infra/
│   ├── k8s/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml               Non-secret env vars
│   │   ├── secret.yaml                  SECRET_KEY, GROQ_API_KEY (replace before apply)
│   │   ├── pvc.yaml                     2Gi PVC for ChromaDB
│   │   ├── backend-deployment.yaml      2 replicas, resource limits, liveness/readiness probes
│   │   ├── backend-service.yaml         ClusterIP
│   │   ├── frontend-deployment.yaml
│   │   ├── frontend-service.yaml        NodePort
│   │   ├── hpa.yaml                     min 2 / max 10, CPU 70% + memory 80%
│   │   └── network-policy.yaml          frontend→backend only; Prometheus allowed
│   └── monitoring/
│       ├── prometheus.yml               Scrape config
│       ├── grafana-datasources.yml      Auto-provision Prometheus datasource
│       └── dashboards/
│           ├── dashboard-provider.yml
│           └── anime-recommender.json   8-panel Grafana dashboard
│
├── .github/workflows/
│   ├── ci.yml                           ruff → mypy → unit tests → integration → build+push
│   └── rag-eval.yml                     RAGAS eval on PRs that touch rag/ code
│
├── scripts/
│   └── build_vector_store.py            One-time CSV → ChromaDB ingestion
│
├── docker-compose.yml                   Full local stack (backend + frontend + prometheus + grafana)
├── .env.example                         Template for required env vars
├── .gitignore
└── plan.md                              This file
```

---

## How to Run

### Prerequisites
- Python 3.11+
- Docker + Docker Compose
- A [Groq API key](https://console.groq.com) (free tier is sufficient)

### Step 1 — Copy data from v1 project
```bash
mkdir data
cp ../P1-Video-SEO-Engine/data/anime_updated.csv data/
```

### Step 2 — Configure environment
```bash
cp .env.example .env
# Edit .env: set SECRET_KEY and GROQ_API_KEY
```

Generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 3 — Build vector store (run once)
```bash
cd backend
pip install -r requirements.txt
python ../scripts/build_vector_store.py --csv ../data/anime_updated.csv
cd ..
```

### Step 4 — Start the full stack
```bash
docker-compose up --build
```

| Service    | URL                          | Credentials     |
|------------|------------------------------|-----------------|
| API docs   | http://localhost:8000/docs   | —               |
| Frontend   | http://localhost:8501        | user/user123    |
| Grafana    | http://localhost:3000        | admin/admin     |
| Prometheus | http://localhost:9090        | —               |

### Step 5 — Run tests
```bash
cd backend
pytest tests/unit/ tests/integration/ -v
```

### Step 6 — Run RAGAS evaluation (requires real GROQ_API_KEY and populated ChromaDB)
```bash
cd backend
python -m tests.evaluation.eval_ragas
```

### Step 7 — Run load test (requires k6 installed)
```bash
k6 run load_tests/k6_script.js
```

### Step 8 — Deploy to Kubernetes (Minikube or GKE)
```bash
# Replace YOUR_REGISTRY in deployment YAMLs with your Docker Hub username first
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/
```

---

## API Reference

### `POST /v1/auth/token`
Obtain a JWT access token.
```json
{ "username": "user", "password": "user123" }
```
Returns: `{ "access_token": "...", "token_type": "bearer", "expires_in": 1800 }`

### `POST /v1/recommend`
Stream anime recommendations. Requires `Authorization: Bearer <token>`.
```json
{ "query": "dark psychological thriller with complex characters" }
```
Returns: SSE stream of text chunks. Final events: `data: [DONE]` and `data: __cost__<usd>`.

Blocked by guardrails if query contains: prompt injection patterns, PII, < 3 chars, > 500 chars.
Rate limited to 10 requests/minute per IP.

### `GET /v1/admin/usage`
Returns total request count, total cost, avg cost per request. **Admin role required.**

### `GET /v1/admin/cost`
Returns cost breakdown including estimated monthly cost. **Admin role required.**

### `GET /health`
Liveness probe. Returns `{ "status": "healthy", "uptime_seconds": ... }`.

### `GET /ready`
Readiness probe. Verifies ChromaDB is accessible. Returns 503 if not ready.

### `GET /metrics`
Prometheus metrics endpoint. Scraped every 15s by the Prometheus container.

---

## Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `http_requests_total` | Counter | Total requests by method, endpoint, status code |
| `http_request_duration_seconds` | Histogram | Request latency by method and endpoint |
| `rag_retrieval_duration_seconds` | Histogram | ChromaDB retrieval time per request |
| `rag_requests_total` | Counter | RAG requests by status (started / success / error) |
| `tokens_used_total` | Counter | Tokens consumed by type (input / output) |
| `cost_usd_total` | Counter | Cumulative LLM API cost in USD |
| `guardrail_violations_total` | Counter | Violations by type (prompt_injection, pii_*, too_short, too_long, empty_output) |
| `active_recommendations` | Gauge | Number of SSE streams currently in progress |

---

## RAG Evaluation

**Framework:** RAGAS  
**Metrics:** `faithfulness` (are claims grounded in retrieved docs?) and `answer_relevancy` (does the answer address the question?)  
**Thresholds:** Both must be ≥ 0.65 for CI to pass  
**Dataset:** 20 golden Q&A pairs covering the main anime preference categories  
**CI trigger:** Any PR that modifies `backend/app/rag/**` or `backend/tests/evaluation/**`

---

## Kubernetes Production Notes

- **HPA** scales the backend between 2 and 10 replicas based on CPU (70%) and memory (80%)
- **PVC** persists the ChromaDB vector store across pod restarts — pre-build it before first deploy
- **NetworkPolicy** restricts traffic: frontend can only reach backend, backend accepts only frontend + Prometheus
- **Secret** values must be replaced in `infra/k8s/secret.yaml` before `kubectl apply`
- **Liveness probe** hits `/health` — restarts pod if it fails 3× in a row
- **Readiness probe** hits `/ready` — removes pod from load balancer until ChromaDB is accessible

---

## Known Limitations (Deliberately Left for Real Production Experience)

These gaps are documented honestly because they require real production traffic to close,
not more portfolio projects:

1. **Multi-tenancy** — all users share one vector store. A real enterprise product would isolate per customer.
2. **Token counting** — uses character estimation (~4 chars/token). Production should use tiktoken or extract from LLM response headers.
3. **USERS_DB is in-memory** — replace with PostgreSQL + proper user service before production.
4. **ChromaDB is single-instance** — not horizontally scalable. Production: Pinecone, Weaviate, or managed pgvector.
5. **No TLS** — add cert-manager + ingress TLS termination for production.
6. **Rate limiting is per-IP** — use per-user (JWT sub) rate limiting in a real multi-tenant deployment.
