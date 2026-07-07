.PHONY: install lint fmt type test check \
        eval-ranking eval-rag eval-gate \
        serve build-backend \
        db services app obs observability langfuse full up upv \
        ps logs down downv seed bootstrap urls \
        helm-lint

# ─── Layered local stack ──────────────────────────────────────────────────────
#   db             = data stores only    (Qdrant + DynamoDB-local + Redis)
#   app            = db + api + web      (fully containerised app tier)
#   obs            = observability tier  (Jaeger + Prometheus + Grafana +
#                                         RedisInsight + Langfuse[web/worker/
#                                         postgres/clickhouse/redis/minio])
#   langfuse       = Langfuse stack ONLY (for isolated boot / debugging)
#   full           = db + app + obs      (everything, 15 services)
#   up             = alias for full      (backwards-compat)
#   upv            = FROM ZERO — wipe volumes + build + start + seed catalog
#   down / downv   = stop full stack (downv also wipes named volumes)
#
# All four compose files declare `name: p2-recommender`, so they share ONE
# docker project + network. The api container reaches jaeger/langfuse-web by
# DNS name if obs is up; if obs is down, telemetry is dropped silently.
#
# `--env-file .env` is passed EXPLICITLY: with compose files in a subdirectory,
# docker compose does NOT auto-load `.env` from CWD. Skipping this makes the
# web build bake fallback keys (Clerk placeholder etc.) into the client bundle.
DC_ENV  := --env-file .env
DC_DATA := docker compose $(DC_ENV) -f infra/compose/docker-compose.data.yml
DC_APP  := docker compose $(DC_ENV) -f infra/compose/docker-compose.data.yml -f infra/compose/docker-compose.app.yml
# `make obs` = Jaeger/Prom/Grafana/RedisInsight + Langfuse (10 services). To bring
# up ONLY the langfuse subset, use `make langfuse` (DC_LF below).
DC_OBS  := docker compose $(DC_ENV) -f infra/compose/docker-compose.observability.yml -f infra/compose/docker-compose.langfuse.yml
DC_LF   := docker compose $(DC_ENV) -f infra/compose/docker-compose.langfuse.yml
DC_FULL := docker compose $(DC_ENV) -f infra/compose/docker-compose.data.yml -f infra/compose/docker-compose.app.yml -f infra/compose/docker-compose.observability.yml -f infra/compose/docker-compose.langfuse.yml

# Native runs (make serve). Shell env overrides Makefile default: API_PORT=2999 make serve
API_PORT ?= 2011


# ─── Basics ───────────────────────────────────────────────────────────────────

install:        ## Sync the uv workspace (Python 3.12)
	uv sync

lint:           ## Ruff lint + format check
	uv run ruff check .
	uv run ruff format --check .

fmt:            ## Ruff format + auto-fix
	uv run ruff format .
	uv run ruff check --fix .

type:           ## mypy on packages/apps/tests
	uv run mypy packages apps tests

test:           ## Run the test suite
	uv run pytest -q

check: lint type test   ## Lint + type-check + test (the green gate)


# ─── Eval ─────────────────────────────────────────────────────────────────────

eval-ranking:   ## Retrieval + ranking eval (NDCG@3, MRR, Recall@3)
	uv run python -m evaluation.ranking.run

eval-rag:       ## Answer-quality eval (custom LLM judge)
	uv run python -m evaluation.ragas.run

eval-gate:      ## CI eval gate — blocks merge on ranking regression vs baseline
	uv run python -m evaluation.ranking.gate


# ─── Native dev  (run the API on the host against the data tier) ──────────────

serve:          ## Run the API on the host with reload (needs `make db`)
	uv run uvicorn api.main:app --app-dir apps --host 0.0.0.0 --port $(API_PORT) --reload

build-backend:  ## Build the API docker image (multi-stage, non-root)
	docker build -f apps/api/Dockerfile -t p2-api .


# ─── Containerised stack — tiered  (start with `db`, layer up) ────────────────

db:             ## tier 1: data stores — Qdrant + DynamoDB-local + Redis
	$(DC_DATA) up -d

services: db    ## Alias for `db` (backwards-compat with older Makefile)

app:            ## tier 2: db + api + web (fully containerised)
	$(DC_APP) up --build -d

obs:            ## observability tier: Jaeger + Prom + Grafana + RedisInsight + Langfuse (10 svc)
	$(DC_OBS) up -d
	@echo ""
	@echo "  Note: obs includes Langfuse — first cold start ~1-3 min (ClickHouse + migrations)."
	@echo "  For just langfuse services in isolation: make langfuse"
	@echo ""
	@$(MAKE) --no-print-directory urls

observability: obs   ## Alias for `obs`

langfuse:       ## Langfuse self-host: web + worker + postgres + clickhouse + redis + minio
	$(DC_LF) up -d
	@echo ""
	@echo "  Langfuse booting — cold start ~1-3 min (ClickHouse warm-up + migrations)."
	@echo "  Watch:   docker logs -f p2-langfuse-web"
	@echo "  Ready:   http://localhost:$${LANGFUSE_UI_PORT:-2008}   (login: $${LANGFUSE_INIT_USER_EMAIL:-admin@example.com} / $${LANGFUSE_INIT_USER_PASSWORD:-changeme})"
	@echo ""
	@$(MAKE) --no-print-directory urls

full:           ## everything: db + app + observability + langfuse
	$(DC_FULL) up --build -d
	@echo ""
	@$(MAKE) --no-print-directory urls

up: full        ## Alias for `full` (backwards-compat with older Makefile)


# ─── Stack control ────────────────────────────────────────────────────────────

ps:             ## Status of every container in the stack
	$(DC_FULL) ps

logs:           ## Tail logs for the whole stack (Ctrl-C to stop)
	$(DC_FULL) logs -f --tail=100

down:           ## Stop + remove containers (KEEPS named volumes)
	$(DC_FULL) down

downv:          ## Stop + remove containers AND wipe all named volumes (DESTRUCTIVE)
	$(DC_FULL) down -v

upv:            ## FROM ZERO: downv + build + start ALL tiers + seed catalog (~5-8 min cold)
	@echo ""
	@echo "  make upv: cold bootstrap from empty volumes."
	@echo "  Wipes: qdrant_data + langfuse_{postgres,clickhouse,redis,minio}_data + others."
	@echo "  Rebuilds everything, re-seeds catalog, re-provisions Langfuse from .env INIT vars."
	@echo ""
	@echo "  [1/4] Wiping named volumes (make downv)..."
	@$(DC_FULL) down -v
	@echo ""
	@echo "  [2/4] Starting data tier (Qdrant + DynamoDB + Redis) and waiting for health..."
	@$(DC_DATA) up -d --wait
	@echo ""
	@echo "  [3/4] Seeding catalog into Qdrant (needs OPENAI_API_KEY for embeddings)..."
	@$(MAKE) --no-print-directory seed
	@echo ""
	@echo "  [4/4] Building + starting app + observability + langfuse..."
	@$(DC_FULL) up --build -d
	@echo ""
	@echo "  Cold bootstrap complete."
	@echo "  Langfuse cold-start migrations continue for ~30-90s in the background;"
	@echo "  the first /chat call may take a moment to trace, then it's steady-state."
	@echo ""
	@$(MAKE) --no-print-directory urls


# ─── Data seeding  (run after the data tier is up) ────────────────────────────

seed:           ## Aggregate CSV → JSON, then embed + index into Qdrant
	uv run python -m core.aggregate
	uv run python -m retrieval.index

bootstrap:      ## FROM SCRATCH: bring app tier up, index catalog, print URLs
	$(DC_APP) up --build -d
	@$(MAKE) --no-print-directory seed
	@echo ""
	@echo "  Bootstrap complete — services up, catalog indexed."
	@echo "  Run 'make obs' to add the observability dashboards."
	@$(MAKE) --no-print-directory urls


# ─── Helm  ────────────────────────────────────────────────────────────────────

helm-lint:      ## Lint the Helm chart + validate rendered manifests
	helm lint ops/helm/p2-recommender
	helm template p2 ops/helm/p2-recommender | kubeconform -summary


# ─── URLs  (prints every host-side endpoint, sourced from .env) ───────────────

urls:           ## Print which URL opens which UI (ports come from .env)
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	echo ""; \
	echo "  P2 Recommender — local URLs   (ports sequenced by startup order in .env)"; \
	echo "  -------------------------------------------------------------------------"; \
	echo "  -- data tier (starts 1st) --"; \
	echo "  Qdrant dashboard      http://localhost:$${QDRANT_HTTP_PORT:-2001}/dashboard"; \
	echo "  Qdrant gRPC           localhost:$${QDRANT_GRPC_PORT:-2002}"; \
	echo "  DynamoDB-local        localhost:$${DYNAMODB_PORT:-2003}   (no UI; table auto-created)"; \
	echo "  Redis                 localhost:$${REDIS_PORT:-2004}   (redis-cli or RedisInsight below)"; \
	echo "  -- observability tier --"; \
	echo "  RedisInsight          http://localhost:$${REDISINSIGHT_PORT:-2005}   (add host=redis port=6379)"; \
	echo "  Jaeger (traces)       http://localhost:$${JAEGER_UI_PORT:-2006}   (service: p2-recommender)"; \
	echo "  Prometheus            http://localhost:$${PROMETHEUS_PORT:-2009}   (Status → Targets)"; \
	echo "  Grafana               http://localhost:$${GRAFANA_PORT:-2010}   (login: $${GRAFANA_ADMIN_USER:-admin}/$${GRAFANA_ADMIN_PASSWORD:-admin})"; \
	echo "  Langfuse (LLM traces) http://localhost:$${LANGFUSE_UI_PORT:-2008}   (login: $${LANGFUSE_INIT_USER_EMAIL:-admin@example.com}/$${LANGFUSE_INIT_USER_PASSWORD:-changeme})"; \
	echo "  -- app tier (starts last) --"; \
	echo "  API docs (Swagger)    http://localhost:$${API_PORT:-2011}/docs"; \
	echo "  API health            http://localhost:$${API_PORT:-2011}/health"; \
	echo "  API metrics (raw)     http://localhost:$${API_PORT:-2011}/metrics"; \
	echo "  Web (Next.js)         http://localhost:$${WEB_PORT:-2012}"; \
	echo "  -------------------------------------------------------------------------"; \
	echo ""
