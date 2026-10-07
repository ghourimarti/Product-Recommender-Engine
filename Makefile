.PHONY: install lint fmt type test check \
        eval-ranking eval-rag eval-gate \
        serve build-backend \
        db services app obs observability langfuse full up upv \
        ps logs down downv seed bootstrap urls wait-api \
        alerts-test helm-lint kind-up kind-down kind-addons kind-images kind-secret kind-deploy \
        kind-argocd kind-gitops kind-smoke kind-all

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

type:           ## mypy on packages/apps/tests + the ops/infra scripts
	uv run mypy packages apps tests ops infra

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


# ─── Alert rules  ─────────────────────────────────────────────────────────────
#   One rules file for compose and Kubernetes (ops/helm/p2-recommender/files/alerts.yaml).
#   promtool runs from the Prometheus image compose uses, so no local install is needed.

PROMTOOL := docker run --rm -v "$(CURDIR):/repo" -w /repo --entrypoint promtool prom/prometheus:v2.55.0

alerts-test:    ## Validate the shared alert rules and run their promtool unit tests (Docker)
	$(PROMTOOL) check rules ops/helm/p2-recommender/files/alerts.yaml
	$(PROMTOOL) test rules tests/promtool/alerts_test.yaml


# ─── Helm  ────────────────────────────────────────────────────────────────────

#   One lint per environment values file. The chart refuses to render without an explicit,
#   immutable image tag, so lint uses a placeholder SHA. Always pass tags with --set-string:
#   plain --set turns an all-digit SHA (e.g. 1234567) into a number.

HELM_CHART        := ops/helm/p2-recommender
HELM_ENVS         := kind doks eks
HELM_LINT_TAG     := 0000000
HELM_LINT_TARGETS := $(addprefix helm-lint-,$(HELM_ENVS))
# Gateway API kinds (HTTPRoute) aren't in the core schemas, so fall back to the community CRD catalog.
KUBECONFORM       := kubeconform -strict -summary -kubernetes-version 1.36.1 -schema-location default \
                     -schema-location "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
.PHONY: $(HELM_LINT_TARGETS)

helm-lint: $(HELM_LINT_TARGETS)   ## Lint + schema-validate the chart for every environment

$(HELM_LINT_TARGETS): helm-lint-%:   ## Lint + schema-validate one environment, e.g. make helm-lint-kind
	helm lint --strict $(HELM_CHART) -f $(HELM_CHART)/values-$*.yaml --set-string image.tag=$(HELM_LINT_TAG)
	helm template p2 $(HELM_CHART) -f $(HELM_CHART)/values-$*.yaml --set-string image.tag=$(HELM_LINT_TAG) | $(KUBECONFORM)


# ─── kind  (Phase 6: local, production-like Kubernetes; $0) ───────────────────
#   The compose stack and a kind cluster don't fit in the 8 GB Docker VM together:
#   run `make down` first. From zero, in order:
#     make kind-up kind-addons kind-images kind-secret kind-deploy kind-smoke
#   PROFILE is the API's auth mode: clerk (default; real Clerk sign-in in the browser) or
#   devauth (minted HS256 tokens, for the k6 drills). `make kind-secret PROFILE=devauth`
#   switches a running cluster and restarts the api.
#   These recipes avoid shell syntax on purpose: run from PowerShell, GNU make on Windows finds
#   no sh.exe and runs recipes in cmd.exe. Logic lives in make functions or the Python scripts.

KIND_CLUSTER ?= p2
KIND_CONTEXT := kind-$(KIND_CLUSTER)
KIND_NS      ?= p2
PROFILE      ?= clerk
KUBECTL      := kubectl --context $(KIND_CONTEXT)
include infra/kind/addons/versions.env

# One tag for both images (infra/kind/image_tag.py): the commit's short SHA, plus a hash of the
# uncommitted image inputs when there are any. A tag never claims to be a commit it isn't, and
# never names two different builds (a reused tag means Kubernetes sees nothing to roll out).
# Computed once, and only for the targets that use it; IMAGE_TAG=... on the command line wins.
ifndef IMAGE_TAG
ifneq ($(filter kind-images kind-deploy kind-argocd kind-gitops kind-all,$(MAKECMDGOALS)),)
IMAGE_TAG := $(shell uv run python infra/kind/image_tag.py)
endif
endif

kind-up:        ## Phase 6: create the kind cluster (1 control-plane + 2 workers, pinned image); skips an existing one
	$(if $(filter $(KIND_CLUSTER),$(shell kind get clusters)),@echo kind cluster $(KIND_CLUSTER) already exists - not recreating it,kind create cluster --name $(KIND_CLUSTER) --config infra/kind/kind-config.yaml)

kind-down:      ## Phase 6: delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)

kind-addons:    ## Phase 6: metrics-server, Envoy Gateway, cert-manager, kube-prometheus-stack (pinned) + Gateway, TLS, alert sink
	$(KUBECTL) apply -f infra/kind/platform/00-namespaces.yaml
	helm upgrade --install metrics-server metrics-server --repo https://kubernetes-sigs.github.io/metrics-server/ \
	  --version $(METRICS_SERVER_VERSION) -n kube-system -f infra/kind/addons/metrics-server.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 5m
	helm upgrade --install eg oci://docker.io/envoyproxy/gateway-helm --version $(ENVOY_GATEWAY_VERSION) \
	  -n envoy-gateway-system --create-namespace -f infra/kind/addons/envoy-gateway.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 5m
	helm upgrade --install cert-manager cert-manager --repo https://charts.jetstack.io \
	  --version $(CERT_MANAGER_VERSION) -n cert-manager --create-namespace -f infra/kind/addons/cert-manager.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 5m
	helm upgrade --install kube-prometheus-stack kube-prometheus-stack --repo https://prometheus-community.github.io/helm-charts \
	  --version $(KUBE_PROMETHEUS_STACK_VERSION) -n monitoring --create-namespace -f infra/kind/addons/kube-prometheus-stack.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 10m
	$(KUBECTL) apply -f infra/kind/platform/
	$(KUBECTL) wait --for=condition=Accepted gatewayclass/eg --timeout=120s
	$(KUBECTL) -n gateway wait --for=condition=Ready certificate/app-localhost --timeout=120s
	$(KUBECTL) -n gateway wait --for=condition=Programmed gateway/public --timeout=180s
	$(KUBECTL) -n monitoring rollout status deployment/alert-sink --timeout=180s

# The web image bakes in its API URL (/api: same origin, through the Gateway) and the Clerk
# publishable key. Both are public; secrets are runtime-only and never reach an image.
kind-images:    ## Phase 6: build api + web at IMAGE_TAG and load them into the kind nodes
	$(eval CLERK_PK := $(shell uv run python -c "from dotenv import get_key; print(get_key('.env', 'CLERK_PUBLISHABLE_KEY') or '')"))
	$(if $(CLERK_PK),,$(error CLERK_PUBLISHABLE_KEY is empty in .env))
	docker build -f apps/api/Dockerfile -t p2-api:$(IMAGE_TAG) .
	@echo docker build apps/web -t p2-web:$(IMAGE_TAG) --build-arg NEXT_PUBLIC_API_URL=/api --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=[CLERK_PUBLISHABLE_KEY from .env]
	@docker build apps/web -t p2-web:$(IMAGE_TAG) --build-arg NEXT_PUBLIC_API_URL=/api \
	  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$(CLERK_PK)
	kind load docker-image --name $(KIND_CLUSTER) p2-api:$(IMAGE_TAG) p2-web:$(IMAGE_TAG)

kind-secret:    ## Phase 6: (re)create p2-secrets from a filtered .env (PROFILE=clerk|devauth); restarts the api
	uv run python infra/kind/kind_secret.py --profile $(PROFILE) --namespace $(KIND_NS) --context $(KIND_CONTEXT)

kind-deploy:    ## Phase 6: install or upgrade the chart at IMAGE_TAG with Helm (before kind-argocd)
	helm upgrade --install p2 $(HELM_CHART) -n $(KIND_NS) --kube-context $(KIND_CONTEXT) \
	  -f $(HELM_CHART)/values-kind.yaml --set-string image.tag=$(IMAGE_TAG) \
	  --rollback-on-failure --wait=watcher --timeout 10m

#   GitOps (step 6G). kind-argocd installs Argo CD and an in-cluster git server, pushes the chart
#   and the apps there, and hands the release from Helm to Argo CD: only Helm's release record is
#   deleted, the running objects stay and Argo CD adopts them. From then on, deploy with
#   `make kind-images kind-gitops` (build, load, push): don't mix in kind-deploy, or Helm and Argo
#   CD fight over the same objects.
kind-argocd:    ## Phase 6: Argo CD (pinned) + in-cluster git server; hand p2 over from Helm to GitOps
	helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm \
	  --version $(ARGO_CD_VERSION) -n argocd --create-namespace -f infra/kind/addons/argo-cd.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 10m
	docker build -q -t p2-git-server:alpine3.22 infra/kind/gitops
	kind load docker-image --name $(KIND_CLUSTER) p2-git-server:alpine3.22
	$(KUBECTL) apply -f infra/kind/gitops/git-server.yaml
	$(KUBECTL) -n argocd rollout status deployment/git-server --timeout=180s
	uv run python infra/kind/gitops_push.py --tag $(IMAGE_TAG) --context $(KIND_CONTEXT)
	$(KUBECTL) -n $(KIND_NS) delete secret -l owner=helm,name=p2 --ignore-not-found
	$(KUBECTL) apply -f ops/argocd/kind/root.yaml
	$(KUBECTL) -n argocd wait --for=create application/p2 --timeout=180s
	$(KUBECTL) -n argocd wait --for=jsonpath={.status.sync.status}=Synced application/p2 --timeout=600s
	$(KUBECTL) -n argocd wait --for=jsonpath={.status.health.status}=Healthy application/p2 --timeout=600s

kind-gitops:    ## Phase 6: push the chart + IMAGE_TAG to the in-cluster git server; Argo CD deploys it
	uv run python infra/kind/gitops_push.py --tag $(IMAGE_TAG) --context $(KIND_CONTEXT)

kind-smoke:     ## Phase 6: smoke-test through the Gateway; AGGREGATE=1 spends one live SerpApi search
	uv run python ops/smoke/smoke.py --auth-mode $(PROFILE) $(if $(AGGREGATE),--aggregate)

# From no cluster to a smoke-tested app in one command (the Phase 6 exit criterion). Helm path;
# run `make kind-argocd` afterwards to hand the release to GitOps.
kind-all: kind-up kind-addons kind-images kind-secret kind-deploy kind-smoke   ## Phase 6: from zero to a smoke-tested app


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
