# How to Verify Each Step Yourself

This reproduces every check the transformation runs. On Windows, `make <target>` works
(via chocolatey make); if it doesn't, run the raw `uv run ...` equivalent shown beside it.

## Prerequisites (one time)

- **uv** installed (it provisions Python 3.12 automatically — you do **not** need 3.12 on your system).
- **Docker Desktop** running (for Qdrant, from Step 3 on).
- A `.env` file at the repo root with your `OPENAI_API_KEY` (copy from `.env.example`):
  ```powershell
  Copy-Item .env.example .env      # then edit .env, set OPENAI_API_KEY=sk-...
  ```

## Install / sync the environment

```bash
uv sync          # or: make install
```
Creates `.venv` with Python 3.12 and all dependencies. Re-run after any dependency change.

> A warning `VIRTUAL_ENV=c:\python314 ... ignored` is harmless — uv correctly uses `.venv`.

## The three always-on quality gates (run anytime)

| Gate | make | raw command |
|---|---|---|
| Lint + format | `make lint` | `uv run ruff check . && uv run ruff format --check .` |
| Types (strict) | `make type` | `uv run mypy packages apps tests` |
| Tests | `make test` | `uv run pytest -q` |

`uv run pytest -q` runs **unit + integration**. Integration tests **auto-skip** if
`OPENAI_API_KEY` is unset or Qdrant isn't reachable, so unit-only runs work with no setup.

---

## Per-step verification

### Step 1 — Scaffold
```bash
uv sync
make lint && make type && make test      # expect: all green, smoke test passes
```

### Step 2 — Data reframe (review → product)
```bash
uv run python -m core.aggregate          # writes data/products.json + docs/data-report.md
uv run pytest -q tests/unit/test_aggregate.py
```
Expect: `reviews=450 products=9 errors=0`. Open `docs/data-report.md` to see per-product stats.

### Step 3 — Qdrant + embeddings + hybrid retrieval  *(needs OPENAI_API_KEY + Docker)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d      # start Qdrant  (make up)
uv run python -m retrieval.index                              # index 9 products
uv run pytest -q tests/integration/test_retrieval.py          # real-services test (3 passed)
```
Health check: open http://localhost:6333/healthz (expect HTTP 200).
Stop Qdrant when done: `docker compose -f infra/compose/docker-compose.yml down` (`make down`).

### Step 4 — Recommender ranking core  *(pure logic; no services needed for tests)*
```bash
uv run pytest -q tests/unit/test_ranking.py tests/unit/test_recommend_service.py
```
Live eyeball (needs Qdrant up + indexed from Step 3):
```bash
uv run python - <<'PY'
import warnings; warnings.filterwarnings("ignore")
from retrieval.store import QdrantHybridStore
from recommender.service import recommend
s = QdrantHybridStore()
for q in ["headphones with the best bass", "cheap bluetooth neckband"]:
    res = recommend(q, s, k=3)
    print(f"\nQ: {q}  (no_match={res.no_match})")
    for r in res.products:
        print(f"  final={r.final_score:.3f} rel={r.relevance_score:.3f} rating={r.rating_score:.3f}  {r.title}")
PY
```
(On PowerShell, replace the `<<'PY' ... PY` heredoc with a `@' ... '@ | uv run python -` here-string.)

### Step 5 — Ranking eval baseline (go/no-go gate)  *(needs OPENAI_API_KEY + Docker)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d   # Qdrant
uv run python -m evaluation.ranking.run                    # writes docs/eval-baseline.md  (make eval-ranking)
uv run pytest -q tests/unit/test_ranking_metrics.py        # metric correctness (8 tests)
```
Expect aggregate ≈ **Recall@3 0.82 / NDCG@3 0.80 / MRR 0.83**. Open `docs/eval-baseline.md`
for the per-query and per-tier (attribute vs semantic) breakdown.

### Step 6 — LangChain RAG chain (grounded explanations)  *(needs an LLM key + Docker)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d   # Qdrant
uv run python -m retrieval.index                           # ensure catalog indexed
uv run pytest -q tests/unit/test_chat_merge.py             # merge + provider-selection (6 tests)
uv run pytest -q tests/integration/test_chat.py            # real-LLM end-to-end chat
```
Live eyeball (PowerShell here-string):
```powershell
@'
from retrieval.store import QdrantHybridStore
from retrieval.index import load_catalog
from recommender.chat import chat
s = QdrantHybridStore(); s.index(load_catalog())
r = chat("headphones with good bass for the gym", [], s, k=3)
print(r.summary)
for it in r.items:
    print(f"- {it.title} -> {it.reason}")
'@ | uv run python -
```
The LLM provider is chosen from your `.env` keys in priority **Groq → OpenAI → Anthropic**
(Decision 4). Reasons are grounded in real reviews; the LLM only writes reasons, never
product facts.

### Step 7 — Answer-quality eval (custom LLM judge)  *(needs OPENAI_API_KEY + Docker)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d   # Qdrant
uv run python -m evaluation.ragas.run                      # make eval-rag -> docs/answer-quality-baseline.md
uv run pytest -q tests/unit/test_ragas_format.py           # format/judge-schema (4 tests)
```
Expect ≈ **answer_relevancy 0.94 / faithfulness 0.56 / context_precision 0.65**. Faithfulness
is the weak metric (documented improvement target). Note: the RAGAS *library* is unusable in
this stack (it hard-imports a removed `langchain_community.chat_models.vertexai`), so this is an
equivalent custom LLM-judge harness — see the baseline file's methodology section.

### Step 8 — FastAPI + DynamoDB chat history (SSE)  *(needs Docker: Qdrant + DynamoDB-local)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d   # Qdrant + DynamoDB-local
uv run python -m retrieval.index                           # ensure catalog indexed
uv run pytest -q tests/unit/test_api_health.py \
               tests/integration/test_history.py \
               tests/integration/test_api.py
```
`test_history.py::test_per_user_isolation` proves the fix for the demo's shared-session bug.
Run the API and hit it:
```bash
make serve     # uv run uvicorn api.main:app --app-dir apps --port 8080 --reload
curl http://localhost:8080/health
curl -X POST http://localhost:8080/recommend -H "Content-Type: application/json" -d "{\"query\":\"good bass headphones\",\"k\":3}"
curl -N -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d "{\"query\":\"good bass headphones\",\"session_id\":\"s1\",\"user_id\":\"alice\",\"k\":2}"
curl http://localhost:8080/metrics | findstr http_requests_total
```

### Step 9 — 4-layer caching  *(needs Docker: Qdrant + Redis)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d   # Qdrant + Redis + DynamoDB-local
uv run pytest -q tests/unit/test_cache.py tests/integration/test_cache_integration.py
```
Live: call `/recommend` twice with the same query — the 2nd is served from cache. Confirm via
metrics:
```bash
curl http://localhost:8080/metrics | findstr cache_hits_total
```
Layers: L0 in-proc version memo · L1 Redis embedding cache · L2 Qdrant semantic cache
(near-duplicate queries) · L3 Redis exact response cache. Bumping `catalog:version` invalidates
L2/L3.

### Step 10 — Auth (JWT) + rate limiting  *(needs Docker: Redis; + Qdrant/keys for happy path)*
```bash
uv run pytest -q tests/unit/test_auth.py tests/unit/test_ratelimit.py
uv run pytest -q tests/unit/test_api_health.py::test_recommend_requires_auth   # 401 without token
```
Live (mint a dev token; works because CLERK_JWKS_URL is unset -> HS256 dev mode):
```powershell
make serve   # in another shell
$tok = uv run python -c "from core.auth import mint_dev_token; print(mint_dev_token('alice'))"
curl http://localhost:8080/recommend -X POST -H "Content-Type: application/json" -d "{\"query\":\"bass\",\"k\":2}"            # 401 (no token)
curl http://localhost:8080/recommend -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d "{\"query\":\"bass\",\"k\":2}"   # 200
```
With a real Clerk instance, set `CLERK_JWKS_URL` in `.env` and send Clerk-issued tokens instead.
Rate limit: 30/min + 500/day per user -> 429 with `Retry-After`.

### Step 11 — Observability (OTel traces + Langfuse)  *(needs Docker: Jaeger)*
```bash
docker compose -f infra/compose/docker-compose.yml up -d    # includes Jaeger (UI :16686, OTLP :4317)
uv run pytest -q tests/unit/test_observability.py
```
See traces end-to-end: set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` in `.env`, then
`make serve` and hit the API — open the **Jaeger UI at http://localhost:16686** (service
`p2-recommender`). For LLM token/cost traces, set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
(Langfuse Cloud free tier or self-host) + `LANGFUSE_HOST`. Both degrade gracefully if unset.

### Step 12 — Security + cost controls + kill-switch  *(Docker: Qdrant + Redis for kill-switch)*
```bash
uv run pytest -q tests/unit/test_security.py            # PII redaction, injection markers, merge resistance
uv run pytest -q tests/integration/test_killswitch.py   # LLM_ENABLED=false -> cards but no tokens
```
- **PII redaction:** queries are logged via `redact_pii` (emails/phones/cards -> `[REDACTED_*]`).
- **Injection resistance:** the LLM only writes *reasons*; product set is fixed by our ranking,
  so injected review text can't add/swap products (`test_merge_ignores_injected_product_ids`).
- **Cost cap:** `max_output_tokens` (default 600) on every LLM call.
- **Kill-switch:** set `LLM_ENABLED=false` in `.env` -> `/chat` returns recommendation cards +
  a `degraded` done event, **no** token stream (LLM fully bypassed). `/recommend` unaffected.

### Step 13 — Failure-mode degradation (circuit breakers)  *(pure chaos tests; no services)*
```bash
uv run pytest -q tests/unit/test_resilience.py
```
Covers (Decision 21): circuit breaker open/half-open; **Qdrant down → popularity-only ranking**
(rating×volume, no vector); **Redis down → cache miss/no-op + rate limiter fails open**. The
API uses `resilient_recommend` (breaker → popularity fallback) on both endpoints, and `/chat`
falls back to a static template if all LLM providers fail.

### Step 14 — Next.js frontend (cards-first streaming)  *(Node/npm; browser for the visual check)*
```bash
cd apps/web
npm install
# NOTE: this repo path contains "&" which breaks npm's .cmd shims on Windows -> invoke binaries
# via node directly (on a path without "&", plain `npm run typecheck` / `npm run build` work):
node node_modules/typescript/bin/tsc --noEmit       # type-check -> no errors
node node_modules/next/dist/bin/next build          # -> "Compiled successfully"
```
Run + verify visually:
```bash
# 1) API up:  make serve   (repo root)
# 2) apps/web/.env.local:
#      NEXT_PUBLIC_API_URL=http://localhost:8080
#      NEXT_PUBLIC_DEV_TOKEN=<from: uv run python -c "from core.auth import mint_dev_token; print(mint_dev_token('web'))">
# 3) start UI:  cd apps/web ; node node_modules/next/dist/bin/next dev   # http://localhost:3000
```
In the browser: enter "good bass earphones for the gym" -> cards appear first, then the
explanation streams token-by-token; "Stop" cancels. Dev token locally; Clerk is the production
auth layer.

### Step 15 — Dockerize + compose parity  *(Docker)*
```bash
docker compose -f infra/compose/docker-compose.yml config     # validate full stack (6 services)
docker build -f apps/api/Dockerfile -t p2-api .               # multi-stage, non-root API image
docker run --rm -p 8080:8080 p2-api                           # curl http://localhost:8080/health -> {"status":"ok"}
```
Whole stack in one command (needs `.env` with API keys at repo root):
```bash
docker compose -f infra/compose/docker-compose.yml up -d --build
# api :8080 · web :3000 · qdrant :6333 · redis :6379 · dynamodb :8000 · jaeger :16686
```
Images run as non-root (uid 10001). Note: the API image is ~725MB (fastembed/onnxruntime +
langchain) — slimming is a hardening item (Phase 5).

---

## Full regression sweep — verify ALL steps at once

```bash
docker compose -f infra/compose/docker-compose.yml up -d     # Qdrant + DynamoDB-local
uv sync                                                       # env in sync

# gates (Steps 1-8 code/logic) -> expect: all checks passed / no issues / 47 passed
uv run ruff check . ; uv run ruff format --check .
uv run mypy packages apps tests
uv run pytest -q

# executable pipelines
uv run python -m core.aggregate            # Step 2  -> reviews=450 products=9 errors=0
uv run python -m retrieval.index           # Step 3  -> indexed 9 products
uv run python -m evaluation.ranking.run    # Steps 4/5/5b -> NDCG@3 0.80 / MRR 0.83 (+reranker A/B)
uv run python -m evaluation.ragas.run      # Step 7  -> answer_relevancy 0.94 / faithfulness 0.56  (~$0.30 LLM)
```
All green = Steps 1-8 are healthy. (`pytest` integration tests auto-skip if Qdrant/DynamoDB/keys
are absent, so unit-only runs work anywhere.)

> This file grows as new steps land (Step 9 caching, Step 10 auth, ...).
