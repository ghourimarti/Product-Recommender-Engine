# ==========================================================================================
#  P2 PRODUCTIQ - conversational, rating-aware product recommender
# ==========================================================================================
#  make help          every target, grouped by section
#  make up            compose stack (app + stores + observability) + the kind cluster
#  make upv           the same from zero: wipe volumes and the cluster, rebuild, re-seed
#  make down          stop everything, keep all data        make downv   ... and delete it
#  make urls          where each UI lives                    make service_ls   ... + logins
#  make verify        call every component, PASS/FAIL each   make check   lint + types + tests
#
#  Recipes are shell-neutral: from PowerShell, GNU make runs them in cmd.exe; from Git Bash,
#  in sh. Logic lives in Python (ops/stack, infra/kind), never in shell syntax.
# ==========================================================================================

.DEFAULT_GOAL := help

.PHONY: help install lint fmt type test check env env-check \
        eval-ranking eval-aggregator eval-rag eval-gate \
        db services seed catalog app serve build-backend wait-api obs observability langfuse \
        full up upv down downv bootstrap ps logs urls service_ls verify \
        kind-start kind-start-create kind-start-restart kind-start-running kind-start-skip \
        kind-stop kind-status kind-up kind-down kind-addons kind-addons-core kind-addons-monitoring \
        kind-images kind-secret kind-deploy kind-redeploy kind-argocd kind-gitops kind-smoke kind-all \
        helm-lint alerts-test

help:           ## Every target, grouped by section
	@$(PY) -m ops.stack.make_help Makefile


# ==========================================================================================
#  1. VARIABLES
# ==========================================================================================
#  DC names all three compose files, so every target sees one project and one network;
#  tiers are picked by service name. --env-file is explicit: compose files in a subfolder
#  don't auto-load .env, and the web build would bake in placeholder keys.
#
#  KIND=0 makes up/upv/down/downv leave Kubernetes alone. KIND_NEED_GB is the free Docker VM
#  memory a kind start needs (lean cluster ~4.2 GB measured, plus headroom).
# ------------------------------------------------------------------------------------------

# Git Bash/MSYS would rewrite /repo in `docker run -w /repo` into a Windows path.
export MSYS_NO_PATHCONV    := 1
export MSYS2_ARG_CONV_EXCL := *

PY       := uv run python
DC       := docker compose --env-file .env -f infra/compose/docker-compose.data.yml \
            -f infra/compose/docker-compose.app.yml -f infra/compose/docker-compose.observability.yml

SVC_DATA := qdrant dynamodb redis
SVC_APP  := api web
SVC_LF   := langfuse-web langfuse-worker langfuse-autologin langfuse-postgres langfuse-clickhouse \
            langfuse-redis langfuse-minio
SVC_OBS  := jaeger prometheus grafana redisinsight cadvisor blackbox-exporter redis-exporter \
            langfuse-redis-exporter postgres-exporter $(SVC_LF)

API_PORT ?= 2011

KIND         ?= 1
KIND_NEED_GB ?= 5
KIND_CLUSTER ?= p2
KIND_CONTEXT := kind-$(KIND_CLUSTER)
KIND_NS      ?= p2
PROFILE      ?= clerk
KUBECTL      := kubectl --context $(KIND_CONTEXT)
include infra/kind/addons/versions.env

# One tag for both kind images: the commit's short SHA, plus a hash of uncommitted image inputs
# (infra/kind/image_tag.py). Computed only for the targets that use it; IMAGE_TAG=... wins.
ifndef IMAGE_TAG
ifneq ($(filter kind-images kind-deploy kind-redeploy kind-argocd kind-gitops kind-all kind-start-create,$(MAKECMDGOALS)),)
IMAGE_TAG := $(shell $(PY) infra/kind/image_tag.py)
endif
endif


# ==========================================================================================
#  2. QUALITY GATES
# ==========================================================================================

install:        ## Sync the uv workspace (Python 3.12)
	uv sync

lint:           ## Ruff lint + format check
	uv run ruff check .
	uv run ruff format --check .

fmt:            ## Ruff format + auto-fix
	uv run ruff format .
	uv run ruff check --fix .

type:           ## mypy on packages, apps, tests and the ops/infra scripts
	uv run mypy packages apps tests ops infra

test:           ## The test suite (offline)
	uv run pytest -q

check: lint type test   ## The green gate: lint + types + tests

env:            ## Rewrite .env and .env.example from ops/env/gen_env.py (keeps every value)
	$(PY) ops/env/gen_env.py

env-check:      ## Fail if .env.example is out of date
	$(PY) ops/env/gen_env.py --check


# ==========================================================================================
#  3. EVAL
# ==========================================================================================
#  eval-gate runs in CI on every PR: recorded fixtures, no services or keys needed.
# ------------------------------------------------------------------------------------------

eval-ranking:   ## Ranking eval on the static catalog (NDCG@3, MRR, Recall@3)
	$(PY) -m evaluation.ranking.run

eval-aggregator: ## Ranking eval on the live-aggregator path, offline (0 SerpApi searches)
	$(PY) -m evaluation.aggregator.run

eval-rag:       ## Answer-quality eval (LLM judge; spends tokens)
	$(PY) -m evaluation.ragas.run

eval-gate:      ## Fail on a ranking regression (both paths)
	$(PY) -m evaluation.aggregator.gate
	$(PY) -m evaluation.ranking.gate


# ==========================================================================================
#  4. DATA TIER  -  Qdrant + DynamoDB local + Redis
# ==========================================================================================

db:             ## Start the data stores
	$(DC) up -d $(SVC_DATA)

services: db    ## Alias for db

seed:           ## Index the committed catalog (data/products.json) into Qdrant (needs OPENAI_API_KEY)
	$(PY) -m retrieval.index

catalog:        ## Rebuild data/products.json from raw reviews (CSV=path); then make seed
	$(PY) -m core.aggregate $(if $(CSV),--csv $(CSV))


# ==========================================================================================
#  5. APP TIER  -  FastAPI + Next.js
# ==========================================================================================

app:            ## Build and start api + web (and the data stores they need)
	$(DC) up --build -d $(SVC_APP)
	@$(MAKE) --no-print-directory wait-api

serve:          ## Run the API on the host with reload (needs make db)
	uv run uvicorn api.main:app --app-dir apps --host 0.0.0.0 --port $(API_PORT) --reload

build-backend:  ## Build the API image alone
	docker build -f apps/api/Dockerfile -t p2-api .

wait-api:       ## Wait up to 90 s for the API's /health
	@$(PY) -m ops.stack.wait_http "http://127.0.0.1:{API_PORT}/health" --name API --timeout 90


# ==========================================================================================
#  6. OBSERVABILITY TIER
# ==========================================================================================
#  Jaeger, Prometheus (+ exporters, blackbox probes, cAdvisor), Grafana, RedisInsight and a
#  self-hosted Langfuse. Nothing asks for a login: Grafana is anonymous, RedisInsight has both
#  Redis databases registered, Langfuse is provisioned from .env and :2019 signs you in.
#  Langfuse's first cold start takes 1-3 min (ClickHouse + migrations).
# ------------------------------------------------------------------------------------------

obs:            ## Start the observability tier
	$(DC) up -d $(SVC_OBS)
	@$(MAKE) --no-print-directory urls

observability: obs   ## Alias for obs

langfuse:       ## Start only Langfuse and its stores
	$(DC) up -d $(SVC_LF)


# ==========================================================================================
#  7. LIFECYCLE  -  compose + kind together
# ==========================================================================================
#      full     compose only: data + app + observability
#      up       full + kind-start          down    compose down + kind-stop  (data kept)
#      upv      downv, rebuild, seed, up   downv   compose down -v + delete the cluster
#
#  A kind failure doesn't stop up/upv (the - prefix): the compose app still comes up, the
#  error stays on screen and `make urls` shows kind as down.
#
#  Nothing restarts by itself after a reboot (no compose restart policies): run make up.
#  kind's nodes are the exception (kind sets their policy); make down stops them.
# ------------------------------------------------------------------------------------------

full:           ## Compose only: data + app + observability (no kind)
	$(DC) up --build -d
	@$(MAKE) --no-print-directory wait-api
	@$(MAKE) --no-print-directory urls

up:             ## Everything: compose stack + kind cluster (KIND=0: compose only)
	$(DC) up --build -d
	@$(MAKE) --no-print-directory wait-api
	-@$(MAKE) --no-print-directory kind-start
	@$(MAKE) --no-print-directory urls

upv:            ## From zero: wipe volumes + the cluster, rebuild, seed, start everything (~15 min)
	@$(MAKE) --no-print-directory downv
	$(DC) build
	$(DC) up -d --wait $(SVC_DATA)
	@$(MAKE) --no-print-directory seed
	$(DC) up -d
	@$(MAKE) --no-print-directory wait-api
	-@$(MAKE) --no-print-directory kind-start
	@$(MAKE) --no-print-directory urls

down:           ## Stop compose and the kind nodes; all data is kept
	$(DC) down
	@$(PY) -m ops.stack.kind stop --cluster $(KIND_CLUSTER) --enabled $(KIND)

downv:          ## DESTRUCTIVE: stop, delete every volume and the kind cluster
	$(DC) down -v
	@$(PY) -m ops.stack.kind delete --cluster $(KIND_CLUSTER) --enabled $(KIND)

bootstrap:      ## Compose app tier from scratch, then seed (no observability, no kind)
	$(DC) up --build -d $(SVC_APP)
	@$(MAKE) --no-print-directory wait-api
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory urls

ps:             ## Compose containers and kind nodes
	$(DC) ps
	@$(PY) -m ops.stack.kind status --cluster $(KIND_CLUSTER)

logs:           ## Follow compose logs (S=api for one service)
	$(DC) logs -f --tail=100 $(S)


# ==========================================================================================
#  8. SERVICE DIRECTORY + VERIFY
# ==========================================================================================
#  urls        every URL with a live up/down mark; no credentials, safe to screen-share
#  service_ls  the same plus local logins (pgAdmin, MinIO, Langfuse, Grafana admin, ...);
#              provider API keys are never printed
#  verify      calls every component and prints PASS/FAIL; LIVE=1 also calls each LLM
#              provider once (a few tokens)
# ------------------------------------------------------------------------------------------

urls:           ## Where every UI lives, with up/down status (no credentials)
	@$(PY) -m ops.stack.directory urls --cluster $(KIND_CLUSTER)

service_ls:     ## Every service with its local logins (provider keys never printed)
	@$(PY) -m ops.stack.directory creds --cluster $(KIND_CLUSTER)

verify:         ## Check every component end to end; LIVE=1 also calls each LLM provider
	@$(PY) -m ops.stack.verify --cluster $(KIND_CLUSTER) $(if $(filter 1,$(LIVE)),--live)


# ==========================================================================================
#  9. LOCAL KUBERNETES (kind)
# ==========================================================================================
#  kind-start creates the LEAN cluster (no in-cluster Prometheus/Grafana; compose watches
#  compose) when there is none, and restarts its nodes when they are stopped. It never starts
#  without KIND_NEED_GB free in the Docker VM, and never touches another project's cluster.
#
#  The full Phase 6 cluster (monitoring + GitOps): make kind-all, then make kind-argocd.
#  PROFILE is the API's auth mode on kind: clerk (browser sign-in) or devauth (k6 drills).
#  After kind-argocd, deploy with kind-images kind-gitops, never kind-deploy.
# ------------------------------------------------------------------------------------------

kind-start:     ## Create the lean cluster if absent, else restart it (skips if memory is short)
	@$(MAKE) --no-print-directory kind-start-$(shell $(PY) -m ops.stack.kind plan --cluster $(KIND_CLUSTER) --enabled $(KIND) --need-gb $(KIND_NEED_GB))

kind-start-create: kind-up kind-addons-core kind-images kind-secret kind-deploy kind-smoke

kind-start-restart:
	@$(PY) -m ops.stack.kind restart --cluster $(KIND_CLUSTER)
	@$(MAKE) --no-print-directory kind-smoke

kind-start-running:
	@$(PY) -m ops.stack.kind drift --cluster $(KIND_CLUSTER)
	@$(MAKE) --no-print-directory kind-smoke

kind-start-skip:
	@echo   kind: not started

kind-stop:      ## Stop the kind nodes; the cluster and its data stay
	@$(PY) -m ops.stack.kind stop --cluster $(KIND_CLUSTER) --enabled $(KIND)

kind-status:    ## Nodes, pods, and whether the deployed image is the current code
	@$(PY) -m ops.stack.kind status --cluster $(KIND_CLUSTER)

kind-up:        ## Create the cluster (1 control plane + 2 workers, pinned image); skips an existing one
	$(if $(filter $(KIND_CLUSTER),$(shell kind get clusters)),@echo kind cluster $(KIND_CLUSTER) already exists - not recreating it,kind create cluster --name $(KIND_CLUSTER) --config infra/kind/kind-config.yaml)

kind-down:      ## DESTRUCTIVE: delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)

kind-addons: kind-addons-core kind-addons-monitoring   ## All add-ons: core + monitoring

kind-addons-core: ## metrics-server, Envoy Gateway, cert-manager + Gateway and TLS (pinned)
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
	$(KUBECTL) apply -f infra/kind/platform/10-envoy-gateway.yaml -f infra/kind/platform/20-certificates.yaml \
	  -f infra/kind/platform/30-gateway.yaml
	$(KUBECTL) wait --for=condition=Accepted gatewayclass/eg --timeout=120s
	$(KUBECTL) -n gateway wait --for=condition=Ready certificate/app-localhost --timeout=120s
	$(KUBECTL) -n gateway wait --for=condition=Programmed gateway/public --timeout=180s

kind-addons-monitoring: ## kube-prometheus-stack + alert sink (~1.3 GB); then make kind-deploy
	helm upgrade --install kube-prometheus-stack kube-prometheus-stack --repo https://prometheus-community.github.io/helm-charts \
	  --version $(KUBE_PROMETHEUS_STACK_VERSION) -n monitoring --create-namespace -f infra/kind/addons/kube-prometheus-stack.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 10m
	$(KUBECTL) apply -f infra/kind/platform/40-alert-sink.yaml
	$(KUBECTL) -n monitoring rollout status deployment/alert-sink --timeout=180s

# The web image bakes in its API URL (/api: same origin, through the Gateway) and the Clerk
# publishable key. Both are public; secrets are runtime-only and never reach an image.
kind-images:    ## Build api + web at IMAGE_TAG and load them into the nodes
	$(eval CLERK_PK := $(shell $(PY) -c "from dotenv import get_key; print(get_key('.env', 'CLERK_PUBLISHABLE_KEY') or '')"))
	$(if $(CLERK_PK),,$(error CLERK_PUBLISHABLE_KEY is empty in .env))
	docker build -f apps/api/Dockerfile -t p2-api:$(IMAGE_TAG) .
	@echo docker build apps/web -t p2-web:$(IMAGE_TAG) --build-arg NEXT_PUBLIC_API_URL=/api --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=[from .env]
	@docker build apps/web -t p2-web:$(IMAGE_TAG) --build-arg NEXT_PUBLIC_API_URL=/api \
	  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$(CLERK_PK)
	kind load docker-image --name $(KIND_CLUSTER) p2-api:$(IMAGE_TAG) p2-web:$(IMAGE_TAG)

kind-secret:    ## (Re)create p2-secrets from an allow-list of .env (PROFILE=clerk|devauth); restarts the api
	$(PY) infra/kind/kind_secret.py --profile $(PROFILE) --namespace $(KIND_NS) --context $(KIND_CONTEXT)

kind-deploy:    ## Helm install/upgrade at IMAGE_TAG; chart monitoring follows the cluster's CRDs
	helm upgrade --install p2 $(HELM_CHART) -n $(KIND_NS) --kube-context $(KIND_CONTEXT) \
	  -f $(HELM_CHART)/values-kind.yaml --set-string image.tag=$(IMAGE_TAG) \
	  --set monitoring.enabled=$(shell $(PY) -m ops.stack.kind monitoring --cluster $(KIND_CLUSTER)) \
	  --rollback-on-failure --wait=watcher --timeout 10m

kind-redeploy: kind-images kind-deploy kind-smoke   ## Ship the working tree to a Helm-managed cluster

# Argo CD + an in-cluster git server; hands the release from Helm to GitOps. Only Helm's
# release record is deleted: the running objects stay and Argo CD adopts them.
kind-argocd:    ## Argo CD (pinned) + git server; hand p2 over from Helm to GitOps
	helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm \
	  --version $(ARGO_CD_VERSION) -n argocd --create-namespace -f infra/kind/addons/argo-cd.yaml \
	  --kube-context $(KIND_CONTEXT) --wait=watcher --timeout 10m
	docker build -q -t p2-git-server:alpine3.22 infra/kind/gitops
	kind load docker-image --name $(KIND_CLUSTER) p2-git-server:alpine3.22
	$(KUBECTL) apply -f infra/kind/gitops/git-server.yaml
	$(KUBECTL) -n argocd rollout status deployment/git-server --timeout=180s
	$(PY) infra/kind/gitops_push.py --tag $(IMAGE_TAG) --context $(KIND_CONTEXT)
	$(KUBECTL) -n $(KIND_NS) delete secret -l owner=helm,name=p2 --ignore-not-found
	$(KUBECTL) apply -f ops/argocd/kind/root.yaml
	$(KUBECTL) -n argocd wait --for=create application/p2 --timeout=180s
	$(KUBECTL) -n argocd wait --for=jsonpath={.status.sync.status}=Synced application/p2 --timeout=600s
	$(KUBECTL) -n argocd wait --for=jsonpath={.status.health.status}=Healthy application/p2 --timeout=600s

kind-gitops:    ## Push the chart + IMAGE_TAG to the in-cluster git server; Argo CD deploys it
	$(PY) infra/kind/gitops_push.py --tag $(IMAGE_TAG) --context $(KIND_CONTEXT)

kind-smoke:     ## Smoke test through the Gateway; AGGREGATE=1 spends one live SerpApi search
	$(PY) ops/smoke/smoke.py --auth-mode $(PROFILE) $(if $(AGGREGATE),--aggregate)

kind-all: kind-up kind-addons kind-images kind-secret kind-deploy kind-smoke   ## Full Phase 6 cluster from zero (with monitoring)


# ==========================================================================================
#  10. HELM + ALERT RULES
# ==========================================================================================
#  One lint per environment values file, with a placeholder image tag (the chart refuses to
#  render without one). Tags go through --set-string: --set turns an all-digit SHA into a
#  number. promtool runs from the Prometheus image compose uses: no local install.
# ------------------------------------------------------------------------------------------

HELM_CHART        := ops/helm/p2-recommender
HELM_ENVS         := kind doks eks
HELM_LINT_TAG     := 0000000
HELM_LINT_TARGETS := $(addprefix helm-lint-,$(HELM_ENVS))
# Gateway API kinds (HTTPRoute) aren't in the core schemas: fall back to the community catalog.
KUBECONFORM       := kubeconform -strict -summary -kubernetes-version 1.36.1 -schema-location default \
                     -schema-location "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
PROMTOOL          := docker run --rm -v "$(CURDIR):/repo" -w /repo --entrypoint promtool prom/prometheus:v2.55.0
.PHONY: $(HELM_LINT_TARGETS)

helm-lint: $(HELM_LINT_TARGETS)   ## Lint + schema-validate the chart for kind, doks and eks

$(HELM_LINT_TARGETS): helm-lint-%:
	helm lint --strict $(HELM_CHART) -f $(HELM_CHART)/values-$*.yaml --set-string image.tag=$(HELM_LINT_TAG)
	helm template p2 $(HELM_CHART) -f $(HELM_CHART)/values-$*.yaml --set-string image.tag=$(HELM_LINT_TAG) | $(KUBECONFORM)

alerts-test:    ## Validate the shared alert rules and run their promtool unit tests
	$(PROMTOOL) check rules ops/helm/p2-recommender/files/alerts.yaml
	$(PROMTOOL) test rules tests/promtool/alerts_test.yaml
