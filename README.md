<div align="center">

# ProductIQ — Conversational Product Recommender

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](#-how-it-works)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%E2%86%92%20OpenAI%20%E2%86%92%20Anthropic-412991?style=flat-square&logo=openai&logoColor=white)](#-tech-stack)
[![Qdrant](https://img.shields.io/badge/Qdrant-Hybrid%20RAG-DC244C?style=flat-square&logo=qdrant&logoColor=white)](https://qdrant.tech)
[![DynamoDB](https://img.shields.io/badge/DynamoDB-Single%20Table-4053D6?style=flat-square&logo=amazondynamodb&logoColor=white)](#%EF%B8%8F-database-schema-chat-history)
[![Redis](https://img.shields.io/badge/Redis-4--Layer%20Cache-DC382D?style=flat-square&logo=redis&logoColor=white)](#-how-it-works)
[![Clerk](https://img.shields.io/badge/Auth-Clerk%20%C2%B7%20JWT-6C47FF?style=flat-square&logo=clerk&logoColor=white)](#-security)
[![Next.js](https://img.shields.io/badge/Next.js-16%20%2F%20React%2019-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Observability](https://img.shields.io/badge/OTel%20%C2%B7%20Langfuse%20%C2%B7%20Prometheus%20%C2%B7%20Grafana-Tracing-F46800?style=flat-square&logo=opentelemetry&logoColor=white)](#-tech-stack)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/K8s-Helm%20%E2%86%92%20EKS-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](#-deployment)
[![Terraform](https://img.shields.io/badge/Terraform-EKS%2FDynamoDB%2FECR-7B42BC?style=flat-square&logo=terraform&logoColor=white)](#-deployment)

[🚀 Quick Start](#-quick-start) · [🧰 Make Commands](#-make-commands) · [✨ Features](#-features) · [🏗️ Architecture](#%EF%B8%8F-architecture) · [📡 API](#-api-reference) · [🐳 Deployment](#-deployment)

</div>

---

## 🌟 What Is This?

**ProductIQ** is a full-stack **conversational product recommender**. You ask in plain language —
*"noise cancelling for the office", "good bass earphones for the gym", "wireless earbuds under
$100"* — and it returns a **ranked shortlist of real, buyable products**, each with a short
explanation of why it fits, streamed to your browser: the **cards appear first**, then the reasons
fill in below.

### One ranking core, two retrieval backends

The interesting part is that **retrieval is pluggable and ranking is not**. The same rating-aware
ranker, cache, guardrails, and eval methodology sit behind both of these:

| | **[A] Your catalog** | **[B] The live web** |
|---|---|---|
| **Endpoints** | `POST /recommend` · `POST /chat` (SSE) | `POST /aggregate` · `POST /aggregate/stream` (SSE) |
| **Retrieval** | **Qdrant hybrid** — dense (OpenAI `text-embedding-3-small`) + sparse (BM25) over an indexed catalog | **SerpApi / Google Shopping** — one live search per cache miss |
| **Relevance from** | semantic similarity score | source result `position` (Google already ordered by relevance) |
| **Data** | `data/products.json` — a **9-product demo catalog**, deliberately small | whatever is live on Google Shopping right now |
| **Binding constraint** | embedding cost at index time | **metered search quota** (250/month free) → global budget guard |
| **Wired to the web UI?** | **No** — API + tests only | **Yes** — the dashboard's Discover page calls this |

**What both backends share:** a ranking blend of
`semantic/positional relevance × average rating × review-volume confidence` — so a 5★-from-2-reviews
product can't outrank a 4.5★-from-500 — and an LLM that writes **only the reasons**, never the
product set. Because ranking is deterministic and the model merely annotates it by `product_id`,
injected text in a review or a listing **cannot add, remove, or reorder a recommendation**.


---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **Rating-Aware Ranking** | The recommender core blends **semantic relevance × avg_rating × review-volume confidence** — a 5★-from-2-reviews product can't outrank a 4.5★-from-500 |
| 🔍 **Hybrid Retrieval** | Qdrant **dense (OpenAI) + sparse (BM25)** hybrid search — catches keyword intent ("neckband", "wired", "bass") that dense-only blurs across near-identical products |
| 💬 **Grounded, Streaming Explanations** | Cards render first, then the LLM explanation **streams token-by-token** (SSE); reasons are grounded **only** in the provided reviews — it surfaces negatives honestly instead of overselling |
| 🔁 **Tiered LLM Gateway + Fallback** | **Groq `llama-3.3-70b` → OpenAI `gpt-4o` → Anthropic** via `with_fallbacks` (key-gated) — single-provider outage ≠ full outage |
| ⚡ **4-Layer Cache** | L0 in-proc version memo · L1 Redis embedding cache · **L2 Qdrant semantic cache** (near-duplicate queries) · L3 Redis exact-response cache — invalidated by a catalog-version bump |
| 🔐 **Auth + Quotas** | **Clerk** JWT (RS256 via JWKS) or dev HS256 · per-user Redis token-bucket **rate limiting** (30/min + 500/day) · the auth subject scopes all per-user data |
| 🛡️ **Security** | Reviews treated as untrusted data · **structural injection-resistance** (LLM writes only reasons; the product set is fixed by ranking) · **PII redaction** in logs · **kill switch** (`LLM_ENABLED=false` → cards without LLM) |
| 🩹 **Graceful Degradation** | **Circuit breaker → popularity-only ranking** when Qdrant/embeddings fail · Redis-down degrades to cache-miss (rate limiter fails open) · all-LLMs-down → static template |
| 📊 **Full Observability** | One request = one **OpenTelemetry** trace → Jaeger · **Langfuse** for per-request LLM token/cost/latency · **Prometheus** RED + cache metrics → **Grafana** |
| 💸 **Global Spend Guard** | The live source is **metered** (250 searches/month free) — the binding constraint on the product, not compute. Per-user rate limits don't protect a **shared** budget: one user inside their own quota can drain everyone's month. Spend is therefore counted **globally in Redis** (day + month) and refused past the cap, with a 6h result cache so a repeat query costs **0 searches and 0 LLM calls** |
| 🚨 **An Outage Is Not an Empty Result** | Any source failure (quota exhausted, bad key, network) used to return `no_match=true` — indistinguishable from "we genuinely found nothing", so **nobody could tell the product was broken**. Failures now return a distinct `source_unavailable` state with a reason and a `source_unavailable_total{reason}` counter — an **alertable** condition |
| 📈 **Eval Gate That Can Fail the Build** | Two guards on every PR: NDCG@3/MRR must hold within tolerance of a frozen baseline, **and our ranking must still beat Google Shopping's own ordering** (ours **0.9413 / 1.0000** vs Google **0.8240 / 0.8750**). If guard 2 breaks, the re-ranker has stopped earning its place and CI goes red rather than shipping it. Runs on recorded fixtures — no services, no keys, no paid quota |
| 🐳 **Deploy Path** | Multi-stage **non-root** Docker · 3-file compose mesh · **Helm** chart (kind → EKS) · **Terraform** (EKS / DynamoDB / ElastiCache / S3 / ECR / IRSA). Local Docker is verified end-to-end; **Helm and Terraform are validated but have never been applied to a live cluster** — see [Results](#-results-real-numbers-honest-scope) |

---

## 🖼️ Screenshots

<div align="center">

### Landing Page
![Landing page](assets/screenshots/landing_page.png)
*The marketing/landing page (`apps/web` App Router).*

### Query & Streaming Recommendations
![Query and streaming recommendations](assets/screenshots/recommend.png)
*Ask in natural language → grounded recommendation cards → the "why it matches" explanation streams in below.*

### Prometheus
![Prometheus target](assets/screenshots/prometheus_target.png)
![Prometheus Rules](assets/screenshots/prometheus_rules.png)
*Prometheus targets + alerting rules — the live SerpApi source is **metered** and the global budget is **guarded** by a Redis counter. A single user inside their own quota can drain everyone's month, so the alerting rules watch for `source_unavailable` and `source_unavailable_total{reason="budget_exceeded"}`.*

### Real-time Monitoring: Graffana
![Grafana API overview dashboard](assets/screenshots/graffana.png)
*Grafana overview dashboard*

### Langfuse
![Langfuse trace detail](assets/screenshots/langfuse_dashboard.png)
![Langfuse trace detail](assets/screenshots/langfuse_runnables.png)
*Langfuse trace detail — the LLM gateway and the Qdrant hybrid store are instrumented with Langfuse runnables, so you can see **per-request LLM cost, latency, and token usage**.*

### JAEGER UI
![JAEGER UI](assets/screenshots/jaeger_dashboard.png)
![JAEGER UI](assets/screenshots/jaeger_search.png)
*Jaeger UI — traces from the FastAPI backend, including the LLM gateway and the Qdrant hybrid store.*

### Qdrant Dashboard
![Qdrant dashboard](assets/screenshots/qdrant_dashboard.png)
*Qdrant dashboard — the hybrid store for the catalog path. The semantic cache is a Qdrant collection that stores embeddings for near-duplicate queries, so a repeat query costs **0 searches and 0 LLM calls**.*

### RedisInsight and Redis cache
![RedisInsight](assets/screenshots/redisinsight.png)
![RedisInsight](assets/screenshots/redis_cache.png)
*RedisInsight — both the app cache and the Langfuse Redis are pre-registered on first boot.*

### MinIO Console
![MinIO Console](assets/screenshots/minio.png)
*MinIO Console (Langfuse S3) — for pgAdmin/DBeaver/psql/MinIO-console access to the Langfuse infra.*
</div>

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│           CLIENT · Next.js 16 / React 19 / Tailwind v4                │
│   Marketing site · Dashboard/Discover · live SSE stream · Clerk auth  │
│   BFF route handlers attach the session token server-side             │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  REST + SSE (EventSource)
┌───────────────────────────┼──────────────────────────────────────────┐
│                     FastAPI  Backend  (async)                         │
│  [B] POST /aggregate · /aggregate/stream   ← what the web UI calls    │
│  [A] POST /recommend · POST /chat (SSE)    ← catalog path, API-only   │
│      DELETE /account · GET /account/export · GET /health · /metrics   │
│  JWT auth (Clerk/dev) · per-user rate limit · kill switch · PII log   │
└──────┬──────────────────────┬────────────────┬──────────────────────┘
       │                      │                │
┌──────┴───────────┐  ┌───────┴────────┐  ┌────┴─────────────┐
│ [A] Qdrant       │  │ [B] SerpApi    │  │  Redis           │
│  hybrid RAG      │  │  Google        │  │  L1 embeddings   │
│  dense + sparse  │  │  Shopping      │  │  L3 responses    │
│  + semantic      │  │  (LIVE, PAID)  │  │  agg cache (6h)  │
│    cache (L2)    │  │                │  │  rate limits     │
└──────┬───────────┘  └───────┬────────┘  │  GLOBAL SerpApi  │
       │                      │           │   spend counter  │
       │                      │           └────┬─────────────┘
       │                      │                │
       │                      │        ┌───────┴──────────┐
       │                      │        │   DynamoDB       │
       │                      │        │  single-table    │
       │                      │        │  chat history    │
       │                      │        │  (per-user PK)   │
       │                      │        │  PITR + TTL      │
       │                      │        └──────────────────┘
       │  candidates          │  offers (rating, reviews, price, store)
       │  (avg_rating,        │
       │   review_count)      │   ── budget exceeded / source down?
       │                      │      → source_unavailable (alertable),
       │                      │        NOT "no match"
┌──────┴──────────────────────┴──────────────────────────────────────────┐
│  SHARED RATING-AWARE RANKER  final = 0.7·relevance + 0.3·rating·volume  │
│  [A] relevance = semantic score   ·   [B] relevance = source position   │
│  → grounded reasons (LangChain structured output; ranker fixes the set) │
└──────┬─────────────────────────────────────────────────────────────────┘
┌──────┼─────────────────────────────────────────────────────────────────┐
│  LLM gateway · Groq llama-3.3-70b → OpenAI gpt-4o → Anthropic (fallback) │
│  max_tokens cap · circuit breaker → popularity fallback on failure      │
└─────────────────────────────────────────────────────────────────────────┘
  Observability: OpenTelemetry → Jaeger · Langfuse (LLM cost) · Prometheus → Grafana
```

### Request Flow

```
[B] LIVE AGGREGATOR — the path the web UI uses

[User]  sign in (Clerk / dev token) → ask: "noise cancelling for the office"
   │
   ▼
POST /aggregate/stream  ──►  auth + per-user rate limit
   │
   ├─► 6h result cache HIT?  ──► emit "final" immediately.  0 searches, 0 LLM calls.
   │
   ├─► MISS → check the GLOBAL day/month SerpApi budget
   │            └─ exhausted? → "final" with source_unavailable  (alertable, NOT no_match)
   │
   ├─► 1 live SerpApi search  ──► rank offers (position × rating × review volume)
   │            └─ search failed? → source_unavailable  (alertable, NOT no_match)
   │
   ├─► SSE event "offers"   ── CARDS RENDER HERE, before the LLM has written anything
   ├─► SSE event "final"    ── grounded reason per offer + summary; result cached 6h
   └─► SSE event "done"

   Why staged: the blocking /aggregate made the user wait for search AND the LLM
   (measured cold 2.94s, breaching the p95 < 2s NFR). Cards now land ~1–1.5s earlier.


[A] CATALOG PATH — API only, not wired to the UI

POST /chat  ──►  auth + rate-limit  ──►  (history-aware rewrite if prior turns)
   │
   ├─► cached_recommend:  L3 exact → L1 embed → L2 semantic → Qdrant hybrid retrieve
   │                       → rating-aware rank  →  RankingResult (cards)
   │
   ├─► SSE "recommendations" → SSE "token"… → SSE "done"  (persist turn to DynamoDB)
   │
   └─► output guardrail: tokens held back 200 chars so a system-prompt leak is caught
        before any of it reaches the client

   (Qdrant down → circuit breaker → popularity-only ranking; LLM down → static template)
```

---

## 🗂️ Project Structure

```
P2-Product-Recommendion-engine/            # uv workspace (monorepo)
├── packages/
│   ├── core/          # config · models (Pydantic) · LLM gateway + fallback · prompts
│   │                  # embeddings · cache (4-layer) · history (DynamoDB) · auth · ratelimit
│   │                  # security (PII/injection) · resilience (circuit breaker) · observability
│   ├── retrieval/     # Qdrant hybrid store · semantic cache · reranker (A/B, gated off) · index
│   ├── recommender/   # rating-aware ranking · offer ranking · aggregator · cached · fallback · chat
│   ├── sources/       # SerpApi (Google Shopping) live offer source
│   └── evaluation/    # aggregator eval + ranking eval (NDCG/MRR/Recall) · LLM judge · CI gates
├── apps/
│   ├── api/           # FastAPI: /health /metrics /recommend /aggregate(+/stream) /chat(SSE)
│   └── web/           # Next.js 16 · Clerk · dashboard/discover · live SSE stream · Tailwind
├── infra/
│   ├── compose/       # docker-compose.{data,app,observability}.yml + prometheus.yml
│   │                  # (Langfuse lives inside observability.yml — there is no separate file)
│   └── terraform/     # VPC · EKS · DynamoDB · ElastiCache · S3 · ECR · IRSA (modular)
├── ops/
│   ├── helm/p2-recommender/   # Helm chart (api/web + Qdrant StatefulSet/redis + HPA + ingress)
│   ├── load/          # k6 load script + dev-token minting
│   └── observability/ # Prometheus alerts + Grafana datasources/dashboards
├── data/products.json                     # 9-product static catalog (the /recommend + /chat path)
├── Makefile · pyproject.toml · uv.lock · .env.example
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 · FastAPI (async) · Pydantic v2 · **uv** workspace |
| **Orchestration** | LangChain (LCEL) · history-aware rewrite · **structured-output** grounded explanations |
| **LLM** | **Groq** `llama-3.3-70b` (primary) → OpenAI `gpt-4o` → Anthropic (fallback, key-gated) |
| **Embeddings** | OpenAI `text-embedding-3-small` @ **1536-d** |
| **Retrieval [A]** | **Qdrant** hybrid (dense + BM25 sparse) · payload filtering · semantic cache collection |
| **Retrieval [B]** | **SerpApi** Google Shopping — live offers (price, store, rating, review count); **metered**, guarded by a global Redis day/month budget + 6h result cache |
| **Reranker** | `bge-reranker-base` cross-encoder (fastembed) — **A/B-tested, gated off** (regressed NDCG) |
| **Primary DB** | **DynamoDB** single-table (chat history, per-user isolation, PITR + TTL) |
| **Cache** | Redis 4-layer (in-proc memo · embedding · semantic → Qdrant · response) |
| **Auth** | **Clerk** (RS256 via JWKS) or dev **HS256** · per-user rate limiting + daily quotas |
| **Security** | PII log redaction · structural prompt-injection resistance · cost caps · kill switch |
| **Resilience** | Circuit breaker → popularity fallback · Redis degrade · LLM static-template fallback |
| **Observability** | OpenTelemetry → Jaeger · **Langfuse** (LLM cost/latency) · Prometheus + Grafana · RedisInsight |
| **Eval** | Ranking (NDCG@3 / MRR / Recall@3) + answer-quality (custom LLM judge) · **CI eval gate** |
| **Frontend** | Next.js 16 · React 19 · TypeScript · Tailwind v4 · framer-motion · Clerk |
| **Deployment** | Docker (multi-stage, non-root) · Helm (kind → EKS) · Terraform · GitHub Actions |

---

## 🚀 Quick Start

> The repo is **driven by a `Makefile`** (`make help` lists every target by section). One command
> brings up the compose stack (app, data stores, observability: 21 containers) **and** a local
> Kubernetes cluster (kind) running the same app behind a Gateway. Host ports live in `.env`
> (`2001–2020`), all bound to `127.0.0.1`.

### Prerequisites
- **Python 3.12** and [`uv`](https://docs.astral.sh/uv/) (uv provisions 3.12 for you)
- **Docker Desktop** with a **12 GB** VM (`~/.wslconfig` on Windows): compose ~4 GB + lean kind
  ~4.2 GB. With less, `make up` still runs compose and skips kind, saying why.
- **kind 0.32, kubectl, Helm 4** for the Kubernetes half (`KIND=0` skips it)
- **GNU make**. Recipes are shell-neutral: PowerShell (cmd.exe) and Git Bash both work.
- An **`OPENAI_API_KEY`** (embeddings for `make seed` and every query; LLM fallback rung) and a
  **Clerk** app (sign-in). **`SERPAPI_API_KEY`** feeds the live aggregator the web UI calls: free
  plan = 250 searches/month, every cache miss spends one, a day/month budget guard is on.
  `GROQ_API_KEY` (primary LLM) and `ANTHROPIC_API_KEY` (last rung) are optional.

### 1 · Install & configure
```bash
git clone <your-repo-url> productiq && cd productiq
uv sync                          # the venv (Python 3.12) + every package
cp .env.example .env             # then fill in the keys: one boxed section per service
```

### 2 · Run everything
```bash
make upv          # FROM ZERO: wipe volumes + cluster, rebuild, seed, start compose + kind (~15 min)
make up           # day to day: compose + kind, data kept (KIND=0: compose only)
make urls         # every URL with a live up/down mark (no credentials)
make service_ls   # the same + local logins: pgAdmin, MinIO, Langfuse, Grafana admin, ...
make verify       # call every component: PASS / WARN / FAIL each (LIVE=1 also pings each LLM)
make down         # stop compose + kind nodes, keep all data   (make downv deletes it all)
```

Nothing asks for a login: **Grafana** is anonymous with 5 provisioned dashboards, **Langfuse** is
provisioned from `.env` and http://localhost:2019 signs you in, **RedisInsight** has both Redis
databases registered. Every LLM call is traced to Langfuse and counted in Prometheus
(`llm_requests_total` by provider and status), so a dead provider key shows up on a dashboard and
as the `LLMProviderFailing` alert, not as a silent fallback bill.

**How to check every component yourself, by browser and by CLI:** [docs/VERIFY.md](docs/VERIFY.md).

### 3 · Quality gate and evals
```bash
make check                       # ruff lint + mypy (strict) + pytest (offline)
make eval-aggregator             # ranking eval of the shipped /aggregate path (offline, $0)
make eval-ranking                # NDCG@3 / MRR / Recall@3 (+ reranker A/B), static catalog
make eval-rag                    # answer quality (custom LLM judge; spends tokens)
# Reports land in reports/; CI baselines are packages/evaluation/{aggregator,ranking}/baseline.json
```

### Service map

`make urls` prints this with live status; `make service_ls` adds the logins.

| Component | URL / connection |
|---|---|
| 🖥 **Web** (Next.js) | http://localhost:2012 (Clerk sign-in) |
| 📡 **API** (FastAPI) | http://localhost:2011/docs · `/health` · `/metrics` |
| 🔎 Qdrant (catalog vectors) | http://localhost:2001/dashboard · gRPC `2002` · API key from `.env` |
| 🗄 DynamoDB local (chats) | `localhost:2003` (no UI; AWS CLI / NoSQL Workbench, any credentials) |
| 🧱 Redis (app cache) | `localhost:2004` (no password) |
| 📊 Grafana | http://localhost:2010 (no login): Service health (home), API & LLM, Data stores, Containers, Overview |
| 📈 Prometheus | http://localhost:2009/targets · `/alerts` (11 rules) |
| 🕸 Jaeger | http://localhost:2006 · OTLP gRPC `2007` |
| 🎭 Langfuse | http://localhost:2019 (signs you in) → UI on `2008` |
| 🧰 RedisInsight | http://localhost:2005 (both Redis DBs pre-registered) |
| 📦 cAdvisor | http://localhost:2020 |
| 🐘 Postgres (Langfuse) | `localhost:2013` (pgAdmin; logins via `make service_ls`) |
| 🗃 ClickHouse (Langfuse) | http://localhost:2014/play · native `2015` |
| 🧵 Redis (Langfuse queue) | `localhost:2016` (password in `.env`) |
| 🪣 MinIO (Langfuse blobs) | http://localhost:2018 console · S3 API `2017` |
| ☸️ **kind** | http://app.localhost · https://app.localhost (local CA) · `kubectl --context kind-p2 -n p2 get pods` |

P2 itself keeps no data in Postgres (chats → DynamoDB, catalog → Qdrant, caches → Redis): the
only Postgres is Langfuse's. The LLMs are hosted (Groq → OpenAI → Anthropic); the only models on
local CPU are fastembed's BM25 (hybrid search) and an optional cross-encoder reranker.

### Native dev (fast loop)
```bash
make db                                   # Qdrant + DynamoDB local + Redis
make seed                                 # index the catalog (once)
make serve                                # API on the host (port 2011, --reload)
cd apps/web && npm install && npm run dev # web on :3000
# The repo path contains "&", which breaks npm's .cmd shims on Windows:
#   node node_modules/next/dist/bin/next dev
```

---

## 🧰 Make Commands

`make help` prints all of them, grouped by the Makefile's sections. The compose stack is three
files under one Docker project (`p2-recommender`); tiers are picked by service name.

### Lifecycle

| Command | What it does |
|---|---|
| `make up` | Compose stack (build + start) → wait for the API → **kind-start** → URL directory. `KIND=0`: compose only. |
| `make upv` | **From zero:** `downv` → build → data tier → `seed` → everything → kind → URLs (~15 min cold). |
| `make down` | Stop compose and the kind nodes. All data and the cluster are kept. |
| `make downv` | ⚠️ Stop, **delete every volume and the kind cluster**. |
| `make full` | Compose only (data + app + observability), never kind. |
| `make db` / `app` / `obs` / `langfuse` | One tier: data stores / api + web / observability / Langfuse alone. |
| `make seed` | Build the catalog JSON and index it into Qdrant (needs `OPENAI_API_KEY`). |
| `make ps` · `make logs S=api` | Containers + kind nodes · follow logs (one service with `S=`). |

### Directory and checks

| Command | What it does |
|---|---|
| `make urls` | Every URL with an up/down mark. No credentials: safe to screen-share. |
| `make service_ls` | Every component with its **local** logins. Provider API keys are never printed (set / missing only). |
| `make verify` | Calls every component and prints PASS / WARN / FAIL (36 checks, read-only, a few seconds). `LIVE=1` adds one tiny call per LLM provider (~$0.0001). |
| `make check` | The green gate: `lint` + `type` + `test`. |
| `make env` · `make env-check` | Rewrite `.env` / `.env.example` from `ops/env/gen_env.py` (values kept) · fail if the example is stale. |
| `make alerts-test` · `make helm-lint` | promtool rule tests (Docker) · lint + schema-check the chart for kind, DOKS, EKS. |

### Kubernetes (kind)

`up` runs **`kind-start`**: no cluster → create the **lean** one (no in-cluster Prometheus/Grafana;
compose's monitoring covers compose) and deploy the current code; stopped → restart its nodes and
wait for the app; running → smoke test. It refuses to start without `KIND_NEED_GB` (6) free in the
Docker VM and names any other kind cluster that holds the memory. It never stops or deletes another
project's cluster.

| Command | What it does |
|---|---|
| `make kind-start` · `kind-stop` · `kind-status` | Start (create / restart) · stop the nodes, keep the cluster · nodes, pods, deployed vs current image. |
| `make kind-redeploy` | Build both images at the working tree's tag, load them, `helm upgrade`, smoke test. |
| `make kind-all` | The full Phase 6 cluster from zero, with kube-prometheus-stack. |
| `make kind-addons-monitoring` | Add kube-prometheus-stack to a lean cluster (~1.3 GB), then `make kind-deploy`. |
| `make kind-argocd` · `kind-gitops` | Hand the release to Argo CD · deploy through git. |
| `make kind-smoke` | Smoke test through the Gateway (`AGGREGATE=1` spends one SerpApi search). |

Details: [docs/runbook-kind.md](docs/runbook-kind.md).

---

## 📋 Environment Variables

`.env.example` is generated by `ops/env/gen_env.py` (`make env`): one boxed section per service,
each holding everything that service needs: its port, URL, credentials and settings (Postgres
user, password, database and port together, and so on). Values never carry trailing comments:
python-dotenv reads `KEY=   # note` as the value `# note`. `make env` rewrites both files and keeps
every value already in `.env` (backup in `.env.bak`).

**Two keys decide what works:**

| Key | Needed for | If missing |
|---|---|---|
| `SERPAPI_API_KEY` | **[B] the live aggregator**: `/aggregate`, so the whole web UI | The UI returns `source_unavailable`. Free plan = 250 searches/month; every cache miss spends one. |
| `OPENAI_API_KEY` | **[A] the catalog path**: embeddings for indexing + retrieval; LLM fallback rung | `/recommend` and `/chat` can't embed. `/aggregate` still ranks, but writes no reasons unless Groq or Anthropic is set. |

`GROQ_API_KEY` (primary, cheapest) and `ANTHROPIC_API_KEY` (last rung) are optional. A key that is
set but dead (expired, out of credit) is not silent: `make verify LIVE=1` says which, and the
`LLMProviderFailing` alert fires while the chain falls back.

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | – | Service status |
| `GET` | `/metrics` | – | Prometheus RED + cache-hit/miss + LLM cost metrics |
| `POST` | `/aggregate` | ✅ | **Live** shopping search (SerpApi) → rank → grounded reasons, cached 6h |
| `POST` | `/aggregate/stream` | ✅ | **SSE**: `offers` (cards) → `final` (reasons) → `done` — the path the web UI uses |
| `POST` | `/recommend` | ✅ | Static-catalog ranking (no LLM), 4-layer cached — fast |
| `POST` | `/chat` | ✅ | **SSE** stream: `recommendations` → `token…` → `done` (grounded, per-user history) |
| `DELETE` | `/history?session_id=` | ✅ | Clear one of the caller's chat sessions |
| `DELETE` | `/account` | ✅ | **Right to be forgotten** — cascade-delete all of the caller's data |
| `GET` | `/account/export` | ✅ | **DSAR** — export all of the caller's stored data |

<sub>Auth is **fail-closed**: every endpoint except `/health` + `/metrics` requires a valid Bearer
JWT (Clerk in prod, or a minted dev token locally); `/health` + `/metrics` stay open for
probes/scrape. Per-user rate limit: **30/min + 500/day** → `429` with `Retry-After`. Erasure
(`DELETE /account`) and export (`GET /account/export`) are **implemented**, not planned.</sub>

### Example: `/recommend`
```json
POST /recommend            Authorization: Bearer <token>
{ "query": "good bass earphones for the gym", "k": 3 }
```
```json
// 200 OK
{
  "products": [
    { "product_id": "ACCEVQZABYWJHRHF", "title": "BoAt BassHeads 100 Wired Headset",
      "avg_rating": 4.22, "review_count": 50, "final_score": 0.942,
      "relevance_score": 1.0, "rating_score": 0.805, "volume_confidence": 1.0 }
  ],
  "no_match": false
}
```

### Example: `/chat` (SSE)
```
event: recommendations           ← cards render first
data: {"products":[...],"no_match":false}

event: token                     ← explanation streams in
data: {"text":"The BoAt BassHeads has strong bass and battery, per reviewers..."}

event: done
data: {"no_match":false}
```

---

## 🧠 How It Works

Steps 1, 4, 5, 6 and 7 are **shared by both backends** — that is the point of the design. Steps 2
and 3 are what differ.

### [B] Live aggregator — `/aggregate/stream` (the path the UI calls)

1. **Authenticate + rate-limit** — per-user JWT + Redis token bucket, as below.
2. **Cache, then *budget*, then search** — a 6h result cache is checked first (a hit costs **0
   searches and 0 LLM calls**). On a miss, the **global** day/month SerpApi budget is checked
   *before* spending, because a per-user limit cannot protect a shared quota. Only then does one
   live search go out.
3. **Fail loudly, not silently** — budget exhausted, bad key, or network error returns
   `source_unavailable` with a reason and increments `source_unavailable_total{reason}`. It is
   **never** reported as "no match", because an outage that looks like an empty result is an
   outage nobody notices.
4. **Rank** → 5. **Explain** → 6. **Observe** → 7. **Degrade** — as below. Cards are emitted
   *before* the LLM runs, so they paint ~1–1.5s earlier.

### [A] Catalog path — `/chat`, `/recommend`

1. **Authenticate + rate-limit** — the Bearer JWT (Clerk or dev HS256) is verified; its subject
   becomes the `user_id` that scopes history + rate-limit buckets (`429` on abuse).
2. **History-aware rewrite** — for follow-ups ("a cheaper one?", "what about for calls?"), a cheap
   LLM call rewrites the message into a standalone query using the DynamoDB-backed chat history.
3. **Cache → retrieve** — `cached_recommend` tries **L3 exact → L1 embedding → L2 semantic** cache,
   then **Qdrant hybrid** (dense + BM25 sparse) retrieval, with `avg_rating`/`review_count` in the
   payload.
4. **Rank** — the recommender blends `final = 0.7·relevance + 0.3·(rating × volume_confidence)`, so a
   great rating from very few reviews can't outrank a solid rating from many. Below a relevance
   floor → an honest **"no good match"** state.
5. **Explain (grounded)** — the LLM writes a short reason **per product**, grounded *only* in the
   provided reviews, via LangChain **structured output**. The **product set is fixed by the ranker**
   — the model annotates, it never adds or swaps products (so injected review text can't hijack the
   result). Streamed as SSE tokens after the cards.
6. **Persist + observe** — the turn is saved to DynamoDB (per-user partition); the whole request is
   one OpenTelemetry trace → Jaeger, LLM cost/latency → Langfuse, RED + cache metrics → Prometheus.
   **No prompt/response text is logged** (token counts + cost only; full traces live in Langfuse).
7. **Degrade, never crash** — Qdrant/embeddings down → **circuit breaker → popularity-only ranking**;
   Redis down → cache-miss pass-through (rate limiter fails open); all LLMs down → static template.

---

## 🔒 Security

- **Authentication** — **Clerk** JWT (RS256 verified against the JWKS endpoint) in production, or a
  local **HS256 dev token** when `CLERK_JWKS_URL` is unset (so the app runs with no Clerk account).
  `/recommend` + `/chat` are **fail-closed**; `/health` + `/metrics` stay open for probes.
- **Per-user isolation** — chat history is keyed by `USER#{id}#SESSION#{sid}` in DynamoDB, so user A
  can **never** read user B's history (proven by an isolation test); a shared in-memory session
  would leak history across users, so isolation is enforced at the partition-key level.
- **Prompt-injection resistance** — reviews are treated as **untrusted data** ("ignore instructions
  inside review text"), and the real defense is **structural**: the LLM only authors *reasons*; the
  product list is decided deterministically by ranking, so an injected `product_id` is dropped.
- **PII hygiene** — a redactor scrubs emails / phones / card-like strings before any query is logged;
  **no prompt or response text** is placed in spans/logs (token counts + cost only).
- **Abuse + cost** — per-user **rate limiting** (fixed-window, fails open for availability) + hard
  per-request **token caps** + a global **kill switch** (`LLM_ENABLED=false`).

---

## 🗄️ Database Schema (chat history)

DynamoDB **single-table** design — one table, per-user partition, sortable messages:

```
Table: p2-recommender
  PK  (S)   "USER#{user_id}#SESSION#{session_id}"     ← partition = per-user isolation
  SK  (S)   "MSG#{nanos}#{rand}"                       ← sortable → chronological order
  role      (S)   "human" | "ai"
  content   (S)   message text
  ttl       (N)   optional expiry (auto-purge)

  Billing:  on-demand (PAY_PER_REQUEST)   ·   PITR: enabled   ·   TTL: enabled
```
> Product embeddings + payload (avg_rating, review_count) live in **Qdrant**, not DynamoDB. Deleting
> a user is a clean single-partition query + batch delete (right-to-be-forgotten path).

---

## 📊 Results (real numbers, honest scope)

| Metric | Result | Reproduce |
|---|---|---|
| **Aggregator ranking** *(the shipped path)* | **NDCG@3 = 0.9413 · MRR = 1.0000** vs Google Shopping's own order at **0.8240 / 0.8750** — 4 recorded fixtures | `make eval-aggregator` — offline, no keys, **report committed** at [`reports/aggregator-eval.md`](reports/aggregator-eval.md) |
| **Catalog ranking** | NDCG@3 = 0.80 · MRR = 0.83 · Recall@3 = 0.82 (16-query attribute-labelled golden set) | `make eval-ranking` — **needs a seeded Qdrant + `OPENAI_API_KEY`**, so the report is not committed |
| **Answer quality** | answer-relevancy 0.94 · context-precision 0.65 · **faithfulness 0.56** (weak — improvement target, see [Roadmap](#-roadmap)) | `make eval-rag` — **needs LLM keys**, report not committed |
| **Reranker A/B** | bge cross-encoder **regressed** NDCG@3 (−0.02) / Recall@3 (−0.07) → **gated off** (measure, don't assume) | part of `make eval-ranking`, same requirements |
| **Tests** | **117** (108 offline + 9 integration-marked) · mypy **strict** clean · ruff clean | `uv run pytest --collect-only -q` |
| **Dependency CVEs** | **0 unignored** — `pip-audit` + `npm audit --omit=dev --audit-level=high` (runtime dependencies) block every PR. First run found 36 Python advisories in 11 packages (incl. `starlette` on the request path) and 3 npm high-severity groups (incl. Next.js SSRF); all cleared by upgrade. Six langchain advisories remain **enumerated by ID**, not suppressed by package — a *new* langchain CVE still fails the build. See [Roadmap](#-roadmap) |
| **Cost** | Search-metered, not compute-bound: SerpApi free tier is 250/month and every cache miss spends one. Global day/month budget guard + 6h result cache. LLM cost capped by `MAX_OUTPUT_TOKENS` + kill switch | `SERPAPI_*` in `.env.example` |
| **Deploy** | Local Docker verified (API image builds, `/health` OK) · Helm chart structurally validated · Terraform **HCL syntax-valid, never applied** | `make helm-lint`, `terraform validate` |

> **Where these numbers come from.** Only the aggregator eval and the test/CVE counts are
> reproducible from a bare clone — the rest need a seeded Qdrant and API keys, so their reports are
> not committed and you are taking them on trust. That distinction is deliberate: the one number
> this project actually gates CI on is the one you can verify yourself, offline, in seconds.
> The 4-fixture aggregator set is a sanity check, not a benchmark, and the report says so itself.


---

## 🐳 Deployment

A clean local → cloud path:

1. **Local Docker** — multi-stage **non-root** images (`api` / `web`) + the 3-file compose mesh;
   `make up` brings up the whole stack; the API image builds and serves `/health`.
2. **Helm** — one chart (`ops/helm/p2-recommender`) with a values file per environment (kind,
   DOKS, EKS): api/web Deployments (**HPA**, PDBs, spread across nodes), **Qdrant** and **Redis**
   StatefulSets on PVCs, a same-origin **Gateway API** route (`/api` → api, `/` → web),
   NetworkPolicies, an idempotent seed Job, and Prometheus Operator objects. Every pod runs Pod
   Security **`restricted`**. ServiceAccount with an **IRSA** slot for EKS.
   ```bash
   make helm-lint                              # helm lint + kubeconform, per environment
   ```
3. **Kubernetes on kind** (local, $0) — `make kind-all` goes from no cluster to a smoke-tested app
   behind Envoy Gateway, with cert-manager and kube-prometheus-stack; `make kind-argocd` hands it
   to **Argo CD**. Production drills pass on it: zero-downtime rollout and git rollback, losing a
   node, Qdrant and Redis outages, HPA scaling, OOMKill, NetworkPolicies, alerting. See
   [docs/runbook-kind.md](docs/runbook-kind.md). No real cloud cluster yet: that's Phases 7–8.
4. **Terraform** — modular **VPC · EKS · DynamoDB · ElastiCache · S3 · ECR · IRSA**; S3 remote-state
   backend stubbed.
   ```bash
   cd infra/terraform && terraform init && terraform validate && terraform plan   # no apply
   ```
5. **CI/CD** — GitHub Actions, four jobs on every push and PR:
   `quality` (ruff → mypy strict → offline tests → **eval gate**) · `frontend` (`tsc` +
   `next build`) · `security` (**`pip-audit` + `npm audit` on the runtime dependencies, both
   blocking**) · `integration` (real Qdrant/Redis/DynamoDB service containers; key-gated tests
   auto-skip). The `security` gate went red on 2026-08-08, when new advisories were published
   against urllib3, cryptography, h2, pyjwt and Next.js (three critical RCEs); upgrades on
   2026-10-07 cleared them.
   The gate (`evaluation.aggregator.gate`) blocks a merge if NDCG@3/MRR regress past tolerance
   **or** if our ordering stops beating Google Shopping's own order. It reads recorded fixtures,
   so it needs no services, no keys, and spends no paid SerpApi quota. The static-catalog gate
   needs a seeded Qdrant + `OPENAI_API_KEY`, so it stays local (`make eval-gate`).
   A separate `kind` workflow installs the chart on a fresh kind cluster for every change to the
   chart or the images (lint, Pod Security `restricted`, readiness, a smoke test; no API keys).
   Its first GitHub run, on 2026-10-07, passed.
   **CD is a skeleton and has never been executed** (0 runs): tag-triggered, OIDC → AWS (no
   long-lived keys) → build/push both images to ECR → `helm upgrade --install` against EKS.
   Argo CD runs on kind (Phase 6); the EKS deploy step still calls Helm directly.

Every step above is reproducible with the `make` targets and commands shown.

---

## 🗺️ Roadmap

- ☁️ **Actually apply the Terraform** — the HCL validates but has never been applied; a real EKS
  deploy (and its bill) is the honest next milestone. This is the single biggest gap between this
  repo and a production system, and it is stated here rather than papered over
- 🧪 **End-to-end tests** — `tsc` and `next build` pass, but nothing exercises the SSE stream or the
  Discover page at request time; a green build is not a green runtime
- 🔐 **LangChain 0.3 → 1.x + Langfuse 2 → 3** — six open CVEs in the langchain family are fixed
  only in 1.x, but `langchain` is pinned `<0.4` because Langfuse 2.x hard-imports
  `langchain.callbacks.base`; bumping it blind trades a known CVE for silently-dead tracing. The
  six IDs are enumerated in the CI audit step, so a *new* langchain CVE still fails the build
- 📚 **Broaden the catalog** — multi-category data so Recall@k becomes a meaningful benchmark (beyond within-category audio)
- 🎯 **Lift faithfulness (0.56)** — tighter grounding prompt + wider context window, proven against the eval gate
- 🔁 **Re-open the reranker** — try title-level reranking (bass/neckband appear in titles) and re-A/B
- 🧠 **Agentic tools** — optional `filter_by_price` / `compare_products` tools behind the chain (LangGraph)
- ⚙️ **Self-hosted inference** — vLLM on an EKS GPU pool once sustained QPS justifies it

---

## 👤 About the Author

<div align="center">

Built by **Zain Ul Abdin** — a **Full-Stack AI / GenAI Engineer** who builds AI systems end to end:
not just the model, but the retrieval, the ranking, the caching, the cost controls, and the
evaluation that proves any of it works. **ProductIQ** is a demo build, not a commercial service —
what it demonstrates is the engineering around an LLM feature: eval gates that can fail a build,
a spend guard on a metered dependency, degradation paths that stay honest under failure, and a
test suite and CVE scan that run on every push.

</div>

### 🧩 What I Build
- 🤖 Agentic AI systems (LangChain · LangGraph · CrewAI — tool use, corrective loops)
- 🔍 RAG & retrieval pipelines (embeddings, hybrid search, reranking, grounding, **evaluation**)
- 🎛️ Full-stack AI apps & LLM-backed APIs (FastAPI · Next.js)
- ☁️ MLOps / LLMOps — Docker, Kubernetes, Helm, Terraform, CI/CD, observability
- 💰 Cost, evaluation & reliability engineering for LLM systems

### 🛠️ Tech I Work With
`Python` · `FastAPI` · `LangChain / LangGraph` · `PyTorch` · `Hugging Face` ·
`Qdrant / FAISS / Chroma / Pinecone` · `OpenAI / Claude / Groq / LLaMA / Mistral` ·
`LoRA / QLoRA / SFT` · `Docker` · `Kubernetes` · `Helm` · `Terraform` ·
`GitHub Actions` · `Prometheus / Grafana / Langfuse` ·
`AWS (EKS · DynamoDB · ECR · S3 · SageMaker)`


---
