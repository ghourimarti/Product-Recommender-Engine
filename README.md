# P2 — Conversational, Rating-aware Product Recommender (Enterprise2)

Production-grade transformation of the `demo/` Flipkart review chatbot into a
content-based, rating-aware **product recommender** with grounded RAG explanations.

- **Decisions:** [docs/decision-log.md](docs/decision-log.md) (24 architecture decisions)
- **Plan:** [docs/transformation-plan.md](docs/transformation-plan.md) (18-step transformation)
- **Source (untouched):** [demo/](demo/)

## Stack (see decision log)

Next.js · FastAPI (Python 3.12) · LangChain · Qdrant (hybrid) · DynamoDB · Redis ·
Clerk · OTel + Langfuse · EKS + Terraform · GitHub Actions + ArgoCD ·
RAGAS / promptfoo / GrowthBook.

## Quickstart (local dev)

Tooling is managed by [uv](https://docs.astral.sh/uv/) (pins Python 3.12 automatically).

```bash
uv sync            # create .venv (Python 3.12) + install dev tools   (or: make install)
make lint          # ruff check + format check
make type          # mypy --strict
make test          # pytest
make up            # docker compose stack (Qdrant/Redis/DynamoDB-local/Langfuse) — from Step 3+
```

On Windows without `make`, run the underlying `uv run ...` commands directly
(see the `Makefile` for the exact lines).

## Layout (Decision 22)

```
apps/{web, api, ingestion}        # Next.js · FastAPI · ARQ ingestion
packages/{core, retrieval, recommender, evaluation}
infra/{terraform, compose}
ops/{langfuse, grafana, argocd, helm}
tests/{unit, integration, e2e, load}
docs/
demo/   old/   Prompts/           # reference / archive / source docs (not modified)
```

> Note: the build-spec refers to the eval package conceptually as `eval`; the
> importable Python package is named **`evaluation`** to avoid shadowing the
> Python builtin `eval`. Makefile targets remain `eval-ranking` / `eval-rag`.
> 
> 
