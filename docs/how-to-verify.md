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

---

## Quick "is everything healthy?" sweep

```bash
docker compose -f infra/compose/docker-compose.yml up -d
uv sync
make lint && make type && make test
```
Green lint + types + all tests passing = the build is in a good state.

> This file grows as new steps land (Step 5 ranking eval, Step 6 chain, Step 8 API, ...).
