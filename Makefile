.PHONY: install lint fmt type test check \
        eval-ranking eval-rag eval-gate \
        serve build-backend \
        db services app obs observability langfuse full up upv \
        ps logs down downv seed bootstrap urls wait-api \
        helm-lint

# ─── Layered local stack ──────────────────────────────────────────────────────
#   db             = data stores only    (Qdrant + DynamoDB-local + Redis)
#   app            = db + api + web      (fully containerised app tier)
#   obs            = observability tier  (Jaeger + Prometheus + Grafana +
#                                         RedisInsight + Langfuse[web/worker/
#                                         postgres/clickhouse/redis/minio])
#   langfuse       = Langfuse subset ONLY (for isolated boot / debugging; part
#                                          of the obs tier, started by name)
#   full           = db + app + obs      (everything, 15 services)
#   up             = alias for full      (backwards-compat)
#   upv            = FROM ZERO — wipe volumes + build + start + seed catalog
#   down / downv   = stop full stack (downv also wipes named volumes)
#
# All three compose files (data / app / observability) declare
# `name: p2-recommender`, so they share ONE docker project + network. Langfuse
# lives inside docker-compose.observability.yml. The api container reaches
# jaeger/langfuse-web by DNS name if obs is up; if obs is down, telemetry is
# dropped silently.
#
# `--env-file .env` is passed EXPLICITLY: with compose files in a subdirectory,
# docker compose does NOT auto-load `.env` from CWD. Skipping this makes the
# web build bake fallback keys (Clerk placeholder etc.) into the client bundle.
DC_ENV  := --env-file .env
DC_DATA := docker compose $(DC_ENV) -f infra/compose/docker-compose.data.yml
DC_APP  := docker compose $(DC_ENV) -f infra/compose/docker-compose.data.yml -f infra/compose/docker-compose.app.yml
# `make obs` = the whole observability tier in ONE file: Jaeger/Prom/Grafana/
# RedisInsight + Langfuse (10 services). Langfuse now lives inside
# docker-compose.observability.yml. To bring up ONLY the Langfuse subset, use
# `make langfuse` — it targets the langfuse-* services by name (LF_SERVICES).
DC_OBS  := docker compose $(DC_ENV) -f infra/compose/docker-compose.observability.yml
DC_LF   := $(DC_OBS)
LF_SERVICES := langfuse-web langfuse-worker langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio
DC_FULL := docker compose $(DC_ENV) -f infra/compose/docker-compose.data.yml -f infra/compose/docker-compose.app.yml -f infra/compose/docker-compose.observability.yml

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

eval-ranking:   ## Retrieval + ranking eval, STATIC catalog path (NDCG@3, MRR, Recall@3)
	uv run python -m evaluation.ranking.run

eval-aggregator: ## Ranking eval for the SHIPPED /aggregate path — offline, 0 SerpApi cost
	uv run python -m evaluation.aggregator.run

eval-rag:       ## Answer-quality eval (custom LLM judge)
	uv run python -m evaluation.ragas.run

# Two gates. The aggregator gate needs no services/keys (recorded fixtures), so it runs on every
# PR; it also fails if our ranking stops beating Google Shopping's own order.
eval-gate:      ## CI eval gates — block merge on ranking regression (static + aggregator paths)
	uv run python -m evaluation.aggregator.gate
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

langfuse:       ## Langfuse self-host ONLY (web + worker + postgres + clickhouse + redis + minio)
	$(DC_LF) up -d $(LF_SERVICES)
	@echo ""
	@echo "  Langfuse booting — cold start ~1-3 min (ClickHouse warm-up + migrations)."
	@echo "  Watch:   docker logs -f p2-langfuse-web"
	@echo "  Ready:   http://localhost:$${LANGFUSE_UI_PORT:-2008}   (login: $${LANGFUSE_INIT_USER_EMAIL:-admin@example.com} / $${LANGFUSE_INIT_USER_PASSWORD:-changeme})"
	@echo ""
	@$(MAKE) --no-print-directory urls

full:           ## everything: db + app + observability + langfuse
	$(DC_FULL) up --build -d
	@$(MAKE) --no-print-directory wait-api
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
	@$(MAKE) --no-print-directory wait-api
	@$(MAKE) --no-print-directory urls


# ─── Data seeding  (run after the data tier is up) ────────────────────────────

seed:           ## Aggregate CSV → JSON, then embed + index into Qdrant
	uv run python -m core.aggregate
	uv run python -m retrieval.index

bootstrap:      ## FROM SCRATCH: bring app tier up, index catalog, print URLs
	$(DC_APP) up --build -d
	@$(MAKE) --no-print-directory wait-api
	@$(MAKE) --no-print-directory seed
	@echo ""
	@echo "  Bootstrap complete — services up, catalog indexed."
	@echo "  Run 'make obs' to add the observability dashboards."
	@$(MAKE) --no-print-directory urls


# ─── Helm  ────────────────────────────────────────────────────────────────────

helm-lint:      ## Lint the Helm chart + validate rendered manifests
	helm lint ops/helm/p2-recommender
	helm template p2 ops/helm/p2-recommender | kubeconform -summary


# ─── wait-api  (poll API /health after boot; used by full/upv/bootstrap) ──────

wait-api:       ## Poll API /health until 2xx (max ~60s). Prints status; exits 0 either way.
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	port=$${API_PORT:-2011}; \
	echo ""; \
	echo "  Waiting for the API to report healthy (up to 60s)..."; \
	echo "  Note: Langfuse cold start can take 1-3 min more (ClickHouse + migrations)."; \
	echo "  First-ever run also needs 'make seed' (or use 'make upv')."; \
	for i in $$(seq 1 60); do \
	  if curl -sfo /dev/null "http://localhost:$$port/health" 2>/dev/null; then \
	    echo "  API healthy at http://localhost:$$port/health"; \
	    exit 0; \
	  fi; \
	  sleep 1; \
	done; \
	echo "  API did not report healthy in 60s. Check: docker logs -f p2-api"; \
	exit 0


# ─── URLs  (prints the P2 service directory, sourced from .env) ───────────────

urls:           ## Print the P2 service directory (URLs, logins, ports; sourced from .env)
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	echo ""; \
	echo "  ========================================================================"; \
	echo "   P2 Recommender - service directory   (open the http:// links below)"; \
	echo "  ========================================================================"; \
	echo ""; \
	echo "  [ OPEN IN BROWSER ]"; \
	echo "    Web app             http://localhost:$${WEB_PORT:-2012}"; \
	echo "    API docs (Swagger)  http://localhost:$${API_PORT:-2011}/docs"; \
	echo "    API health          http://localhost:$${API_PORT:-2011}/health"; \
	echo "    API metrics (raw)   http://localhost:$${API_PORT:-2011}/metrics"; \
	echo "    Qdrant dashboard    http://localhost:$${QDRANT_HTTP_PORT:-2001}/dashboard"; \
	echo "    Jaeger (traces)     http://localhost:$${JAEGER_UI_PORT:-2006}     (service: p2-recommender)"; \
	echo "    Langfuse (LLM)      http://localhost:$${LANGFUSE_UI_PORT:-2008}"; \
	echo "        login:          $${LANGFUSE_INIT_USER_EMAIL:-admin@example.com} / $${LANGFUSE_INIT_USER_PASSWORD:-changeme}"; \
	echo "    Prometheus          http://localhost:$${PROMETHEUS_PORT:-2009}     (Status > Targets)"; \
	echo "    Grafana (metrics)   http://localhost:$${GRAFANA_PORT:-2010}     (Prometheus DS + dashboards pre-provisioned)"; \
	echo "        login:          $${GRAFANA_ADMIN_USER:-admin} / $${GRAFANA_ADMIN_PASSWORD:-admin}"; \
	echo "    RedisInsight        http://localhost:$${REDISINSIGHT_PORT:-2005}     (both p2-redis + p2-langfuse-redis pre-added)"; \
	echo "    MinIO console       http://localhost:$${LANGFUSE_MINIO_CONSOLE_PORT:-2018}"; \
	echo "        login:          minio / $${LANGFUSE_MINIO_ROOT_PASSWORD:-langfuse-local-dev}"; \
	echo ""; \
	echo "  [ DATA TIER ]  (client tools - no web UI)"; \
	echo "    Qdrant HTTP/gRPC    localhost:$${QDRANT_HTTP_PORT:-2001} / localhost:$${QDRANT_GRPC_PORT:-2002}   (or dashboard above)"; \
	echo "    DynamoDB local      localhost:$${DYNAMODB_PORT:-2003}   (no UI; table auto-created on first API call)"; \
	echo "    Redis (app cache)   localhost:$${REDIS_PORT:-2004}   no password   (or RedisInsight above)"; \
	echo ""; \
	echo "  [ OBSERVABILITY TIER ]  (make obs)"; \
	echo "    OTLP receiver       localhost:$${OTEL_OTLP_GRPC_PORT:-2007} gRPC   (api sends spans to jaeger:4317 inside the network)"; \
	echo "    Langfuse Postgres   localhost:$${LANGFUSE_POSTGRES_PORT:-2013}"; \
	echo "        login:          user=$${LANGFUSE_POSTGRES_USER:-langfuse} / password=$${LANGFUSE_POSTGRES_PASSWORD:-langfuse-local-dev} / db=$${LANGFUSE_POSTGRES_DB:-langfuse}   (psql / pgAdmin / DBeaver)"; \
	echo "    Langfuse ClickHouse http://localhost:$${LANGFUSE_CLICKHOUSE_HTTP_PORT:-2014}   (HTTP query; native: localhost:$${LANGFUSE_CLICKHOUSE_NATIVE_PORT:-2015})"; \
	echo "    Langfuse Redis      localhost:$${LANGFUSE_REDIS_PORT:-2016}   password=$${LANGFUSE_REDIS_AUTH:-langfuse-local-dev}"; \
	echo "    MinIO S3 API        http://localhost:$${LANGFUSE_MINIO_API_PORT:-2017}   (console is above)"; \
	echo ""; \
	echo "  Metrics flow: app -> Prometheus (/metrics scrape) -> Grafana; traces -> Jaeger; LLM traces -> Langfuse."; \
	echo "  ========================================================================"; \
	echo ""
