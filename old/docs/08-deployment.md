# Phase 6 — Deployment Sequence

Six rungs, each with a **promotion gate** that must pass before the next. Do not skip rungs.
Prereqs: `docker`, `kind`, `kubectl`, `helm`, `terraform`, `k6`, an AWS account, and a local
`.env` (Groq/HF keys). Never paste secrets into git or chat.

---

## Rung 1 — Local Docker (your machine, containers)
**Differs from dev:** no orchestration, no auth (`AUTH_ENABLED=false`), sample corpus, local volumes.
```bash
cp backend/.env.example backend/.env      # fill GROQ_API_KEY (+ HF if using HF embeddings)
docker compose up --build -d
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m scripts.ingest
docker compose ps                          # all healthy?
curl -s localhost:8000/healthz             # {"status":"ok"}
k6 run -e BASE_URL=http://localhost:8000 load_tests/smoke.js
```
**Gate:** all containers healthy; `/readyz` 200; smoke test passes; a manual `/chat` returns a grounded answer with citations.

---

## Rung 2 — Local Kubernetes (kind)
**Differs from rung 1:** real manifests, probes, services discover by name, secrets externalized, HPA present (no real load yet).
```bash
kind create cluster --config infra/helm/kind-config.yaml
# load locally-built images into kind (or push to a local registry)
kind load docker-image recommender-backend:latest recommender-frontend:latest recommender-embedding:latest
helm lint infra/helm/recommender
helm template rec infra/helm/recommender --set localDeps.enabled=true | kubectl apply --dry-run=client -f -
helm install rec infra/helm/recommender \
  --set localDeps.enabled=true --set ingress.enabled=false \
  --set secrets.createSecret=true --set secrets.groqApiKey=$GROQ_API_KEY
kubectl get pods -w
kubectl port-forward svc/recommender-backend 8000:8000 &
curl -s localhost:8000/readyz
```
**Gate:** all pods Ready; readiness gates correctly (kill a dep pod → `/readyz` flips, recovers); secrets sourced from a Secret, not baked into images.

---

## Rung 3 — Terraform plan against a real cloud account (NO apply)
**Differs:** real VPC/EKS/RDS/Redis/ECR; review only.
```bash
cd infra/terraform
# one-time bootstrap of the state bucket + lock table (separate, minimal TF or console)
terraform init -backend-config="bucket=<your-tfstate-bucket>"
terraform fmt -check && terraform validate
terraform plan -var-file=dev.tfvars -out=dev.plan
```
**Gate:** `validate` clean; `plan` creates exactly the expected resources (VPC, EKS, RDS, ElastiCache, ECR, Secrets, Budgets, log group) and **no destroys**; cost estimate reviewed (Infracost optional).

---

## Rung 4 — Dev environment in cloud
**Differs from rung 2:** real managed data (RDS/ElastiCache), images from ECR, OIDC-based CD, small node pool, `AUTH_ENABLED=true` (Cognito), real (small) corpus.
```bash
terraform apply dev.plan
aws eks update-kubeconfig --name recommender-dev
# CD (push to main) builds+scans+pushes images and runs:
#   helm upgrade --install rec infra/helm/recommender --set image.registry=$ECR ... --set *.tag=$SHA
kubectl run migrate --rm -it --image=$ECR/recommender-backend:$SHA -- alembic upgrade head
kubectl run ingest  --rm -it --image=$ECR/recommender-backend:$SHA -- python -m scripts.ingest
k6 run -e BASE_URL=https://dev.<domain> -e TOKEN=<jwt> load_tests/smoke.js
```
**Gate:** smoke passes against the cloud URL; Langfuse shows traces; Prometheus scraping; **run `eval/run_eval.py` against dev → RAGAS thresholds pass** (this is your first real quality number).

---

## Rung 5 — Staging (production-like; load test here)
**Differs from dev:** separate account/namespace, production-like data volume (1–5M vectors), prod-sized nodes, full observability + alerting, real domain + TLS.
```bash
terraform apply -var-file=staging.tfvars
# CD promotes the SAME image digest from dev to staging (no rebuild)
k6 run -e BASE_URL=https://staging.<domain> -e TOKEN=<jwt> load_tests/chat_load.js
```
**Gate (the big one):** k6 meets Phase-1 NFRs — **p95 < 2s, p99 < 4s, error rate < 1%** at 300 RPS peak. Record p50/p95/p99, cache hit-rate, and cost/request (from `/metrics`). Run a **chaos drill** (kill LLM provider creds / scale Qdrant to 0 / kill Redis) and confirm graceful degradation. Do an **RDS restore drill**. Only promote if all pass.

---

## Rung 6 — Production (gated promotion)
**Differs from staging:** real users, prod secrets, multi-AZ RDS, autoscaling headroom, dashboards + paging **live before traffic**, CDN.
```bash
terraform apply -var-file=prod.tfvars
# CD: manual approval (GitHub prod environment) -> promote same digest
# Dashboards (Grafana) + Alertmanager paging confirmed BEFORE cutover.
helm upgrade --install rec infra/helm/recommender -f infra/helm/values-prod.yaml --set *.tag=$SHA --wait
```
**Gate:** canary/small-traffic first; monitor SLO burn for 30–60 min; **rollback ready**: `helm rollback rec` on error-rate or p99 alert. Cost alerts (AWS Budgets 80% of $2.5k) armed.

---

## What each environment changes (summary)
| | Data | Scale | Secrets | Domain | Auth | Observability |
|---|---|---|---|---|---|---|
| Local | sample CSV | 1 replica | `.env` | localhost | off | compose Prom/Grafana |
| kind | sample | HPA defined | k8s Secret | port-forward | off | in-cluster |
| dev | small real | small pool | Secrets Mgr+ESO | dev.\<domain\> | Cognito | Langfuse+Prom |
| staging | prod-like 1–5M | prod-sized | Secrets Mgr | staging.\<domain\> | Cognito | full + alerts |
| prod | real | autoscale+multi-AZ | Secrets Mgr | \<domain\>+CDN | Cognito | full + paging |

## Rollback (any rung)
`helm rollback rec` (app) · `terraform apply` previous plan (infra) · repoint `VECTOR_COLLECTION_NAME` (bad re-index). Triggers: error-rate/p99 alert, failed smoke, cost spike.
