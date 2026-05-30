# Product Recommender — Enterprise (Production-grade RAG)

Enterprise transformation of the Flipkart product-recommender demo into a production-grade
RAG application (Package 1). This repo is being built **layer by layer** following the
decision and transformation records in [`docs/`](docs/).

## Documents (read in order)
1. [`docs/01-career-assessment.md`](docs/01-career-assessment.md) — skill audit & gap list
2. [`docs/02-market-positioning.md`](docs/02-market-positioning.md) — positioning & pricing
3. [`docs/03-service-packages-build-spec.md`](docs/03-service-packages-build-spec.md) — full build-specs
4. [`docs/04-phase1-requirements.md`](docs/04-phase1-requirements.md) — functional + NFR targets
5. [`docs/05-phase2-decision-log.md`](docs/05-phase2-decision-log.md) — 22 architecture decisions
6. [`docs/06-phase3-transformation-plan.md`](docs/06-phase3-transformation-plan.md) — 24-step plan

## Target architecture (locked — see Decision Log)
FastAPI · Next.js · Qdrant · Postgres · Redis · self-hosted bge embeddings · Groq (tiered + fallback) ·
Langfuse + OpenTelemetry · Cognito · Docker · EKS + Helm · Terraform · GitHub Actions.

## Repo layout
```
backend/          FastAPI service (app/{api,core,rag,observability,schemas,workers}) + tests
embedding-service/ self-hosted bge-base embedding microservice (Step 10)
frontend/         Next.js app (Step 18)
infra/            terraform / helm / monitoring (Steps 20-21)
eval/             golden dataset + RAGAS runner (Step 5)
load_tests/       k6 scripts (Step 23)
docs/             decision & transformation records
```

## Quickstart (full stack)
```bash
docker compose up --build
docker compose run --rm backend alembic upgrade head      # migrate
docker compose run --rm backend python -m scripts.ingest  # load corpus (needs GROQ key)
# UI http://localhost:3000 · API http://localhost:8000 · Grafana http://localhost:3001
```
Operations: [`docs/runbook.md`](docs/runbook.md) · Architecture: [`docs/architecture.md`](docs/architecture.md)

## Local dev (backend only)
> Use **Python 3.12** (the ML stack lacks 3.13/3.14 wheels).
```bash
cd backend
python3.12 -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # fill in keys
pytest                 # 53 tests
uvicorn app.main:app --reload --port 8000
```

## Build status (Phase 4 transformation — complete)
- [x] 1 scaffold · 2 FastAPI · 3 abstraction · 4 Qdrant · 5 eval · 6 hybrid+rerank
- [x] 7 Postgres · 8 history fix · 9 SSE · 10 embedding svc · 11 cache · 12 auth · 13 rate/cost
- [x] 14 security · 15 tiering · 16 degradation · 17 observability
- [x] 18 frontend · 19 docker · 20 helm · 21 terraform · 22 CI/CD · 23 load test · 24 docs

Next: Phase 5 hardening · Phase 6 cloud deployment · Phase 7 portfolio writeup.
