# Run From Scratch — Complete Setup & Test Guide

How to stand up and **test every component** of this project on a brand-new machine, in the
correct **boot order**. Each stage says what it needs first, the exact commands, expected output,
and how to know it worked.

**Status legend** (honest about what's been run):
`✅ VERIFIED` = run on this machine, output shown · `🔑 NEEDS KEY` · `🐳 NEEDS DOCKER` ·
`☁️ NEEDS CLOUD/TOOL` (write-once, run in Phase 6 / on a real cluster).

> **Windows path caveat:** this repo's path contains `&` ("Generative AI & ML"), which breaks
> npm's `.cmd` shims. On such a path, invoke Node binaries directly (`node node_modules/...`).
> On a clean machine, **clone into a path with no spaces/`&`** (e.g. `C:\dev\p2-recommender`) and
> plain `npm run ...` works. The Python side is unaffected.

---

## Port scheme (single source of truth)

Every port lives in the **2000-range**, sequenced by boot order. Change any of them in `.env`
and nothing else needs editing — every service reads its host port from there.

| Boot order | Service | Host port | Container internal | `.env` variable |
|---|---|---|---|---|
| 1 | Qdrant (vector DB) HTTP | **2001** | 6333 | `QDRANT_HTTP_PORT` |
| 2 | Qdrant gRPC | **2002** | 6334 | `QDRANT_GRPC_PORT` |
| 3 | DynamoDB local (chat history) | **2003** | 8000 | `DYNAMODB_PORT` |
| 4 | Redis (cache + rate limit) | **2004** | 6379 | `REDIS_PORT` |
| 5 | RedisInsight *(reserved)* | **2005** | — | `REDISINSIGHT_PORT` |
| 6 | Jaeger UI | **2006** | 16686 | `JAEGER_UI_PORT` |
| 7 | OTLP gRPC receiver | **2007** | 4317 | `OTEL_OTLP_GRPC_PORT` |
| 8 | Langfuse UI *(reserved)* | **2008** | — | `LANGFUSE_UI_PORT` |
| 9 | Prometheus *(reserved)* | **2009** | — | `PROMETHEUS_PORT` |
| 10 | Grafana *(reserved)* | **2010** | — | `GRAFANA_PORT` |
| 11 | **API** (FastAPI backend) | **2011** | 2011 | `API_PORT` |
| 12 | **Web** (Next.js frontend) | **2012** | 2012 | `WEB_PORT` |

Boot order in one sentence: **storage tier first** (Qdrant → DynamoDB → Redis) → **observability
receivers** (Jaeger/OTLP) → **API** (needs Qdrant + Redis + DynamoDB) → **Web** (needs API).

**Reserved** = the port slot exists in `.env` so you can add the service later without renumbering.
It is *not* started by `docker compose up` in this project's default stack.

`docker compose` maps the host port on the left to the well-known internal port on the right, so
`p2-api` reaches `p2-qdrant` at `http://qdrant:6333` (container name + internal port), while you
reach it from your browser at `http://localhost:2001`.

---

## TL;DR — minimum happy path (working `/recommend` in ~5 commands)

```bash
uv sync                                     # env (auto-pins Python 3.12)
cp .env.example .env                        # then put OPENAI_API_KEY (+ GROQ_API_KEY) in it
make db                                     # data tier: qdrant + redis + dynamodb
uv run python -m core.aggregate && uv run python -m retrieval.index   # index catalog
make serve                                  # API at http://localhost:2011
```
Then: mint a token and call `/recommend` (Stage 8). Zero keys still runs the **unit tests**.

Even faster (one command, containerised app tier + seeded catalog):
```bash
make bootstrap                              # brings the app tier up + seeds Qdrant
make urls                                   # prints every host-side URL
```

## Tiered stack — pick what you need

The compose stack is split into **three files** by role. Each `make` target below layers on the
previous, so a bigger stack is always a superset of the smaller one.

| Target | Brings up | Compose file(s) |
|---|---|---|
| `make db` | Qdrant, DynamoDB-local, Redis | `docker-compose.data.yml` |
| `make app` | db + api + web | `data.yml` + `app.yml` |
| `make obs` | Jaeger + Prom + Grafana + RedisInsight **+ Langfuse** (10 svc) | `observability.yml` + `langfuse.yml` |
| `make langfuse` | Langfuse subset only (6 svc: web/worker/pg/ch/redis/minio) | `docker-compose.langfuse.yml` |
| `make full` | db + app + obs (everything, 15 services) | all four |
| `make down` | stop + remove containers (keeps volumes) | all four |
| `make downv` | stop + remove containers + **wipe named volumes** (destructive) | all four |
| `make upv` | **from zero**: `downv` → build → start ALL tiers → seed catalog | all four |

`make obs` includes Langfuse by default — one command brings up every telemetry surface. Use
`make langfuse` only when you want the Langfuse subset in isolation (debugging its own boot,
tailing its logs without the rest of obs in the way).
| `make down` | stops + removes containers, keeps volumes | all three |
| `make downv` | stops + removes containers, **wipes named volumes** | all three |
| `make ps` / `make logs` / `make urls` | status / logs / URL cheat-sheet | — |

Aliases kept for backward-compat: `make services` → `make db`, `make observability` → `make obs`,
`make up` → `make full`.

All three compose files share `name: p2-recommender`, so they end up in one docker project on one
network. That means the api container reaches `jaeger` by DNS name **if obs is up**, and OTel spans
are dropped silently if it isn't. You can bring tiers up in any order.

---

## Dependency / sequence map

```mermaid
flowchart TD
  T[Stage 0: tools] --> S[Stage 1: uv sync]
  S --> E[Stage 2: .env keys + ports]
  S --> G[Stage 3: lint/type/unit tests]
  E --> I[Stage 4: docker compose up  (2001–2007)]
  I --> D[Stage 5: aggregate + index]
  D --> Q[Stage 6: query / eval]
  D --> B[Stage 7: backend API  (2011)]
  B --> X[Stage 8: auth/limits/cache/obs/security/killswitch/breakers/GDPR]
  B --> F[Stage 9: frontend  (2012)]
  Q --> C[Stage 10: eval gate / CI-locally]
  B --> K[Stage 11: docker images / full stack]
  K --> H[Stage 12: helm / k8s]
  H --> TF[Stage 13: terraform]
  C --> CI[Stage 14: CI/CD]
```
**Hard ordering:** keys+Docker → index → (query / API) → everything else. The API needs Qdrant +
Redis up and the catalog indexed; `/chat` additionally needs DynamoDB + an LLM key.

---

## Stage 0 — Prerequisites & tooling  `✅ VERIFIED present here: git, uv, docker, node, npm, kubectl, helm, terraform, make` (k6 absent)

| Tool | Why | Install | Verify |
|---|---|---|---|
| **git** | clone | git-scm.com | `git --version` |
| **uv** | Python env + runner (pins 3.12 — host Python version irrelevant) | `pipx install uv` / `winget install astral-sh.uv` / `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| **Docker Desktop** | Qdrant/Redis/DynamoDB/Jaeger + images | docker.com | `docker --version` |
| **Node 22 + npm** | frontend | nodejs.org | `node --version` |
| kubectl | k8s | k8s.io | `kubectl version --client` |
| helm | chart | helm.sh | `helm version` |
| terraform | IaC | hashicorp | `terraform version` |
| k6 *(optional)* | load test | grafana.com/k6 | `k6 version` |
| make *(optional)* | shortcuts (Windows: chocolatey) | — | `make --version` |

You do **not** need Python pre-installed — `uv` downloads 3.12 itself.

## Stage 1 — Clone + create the env  `✅ VERIFIED`

```bash
git clone <repo-url> p2-recommender   # use a path WITHOUT spaces/& on Windows
cd p2-recommender
uv sync                               # creates .venv (Python 3.12) + installs everything
```
Monorepo layout: `apps/{api,web}` · `packages/{core,retrieval,recommender,evaluation}` ·
`infra/{compose,terraform}` · `ops/{helm,observability,load}` · `tests/` · `docs/`.
> Harmless warning `VIRTUAL_ENV=... does not match .venv` — uv correctly uses `.venv`.

## Stage 2 — Secrets / `.env`  `🔑`

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```
The `.env.example` is the **single source of truth** for every port and every credential. Sections:

| Section | Vars | Notes |
|---|---|---|
| **Storage tier ports** (2001–2005) | `QDRANT_HTTP_PORT`, `QDRANT_GRPC_PORT`, `DYNAMODB_PORT`, `REDIS_PORT`, `REDISINSIGHT_PORT` | Host-side ports for browser/native access. Compose reads these. |
| **Storage URLs** | `QDRANT_URL`, `DYNAMODB_ENDPOINT`, `REDIS_URL`, `QDRANT_API_KEY`, `REDIS_PASSWORD` | For **native** runs (`make serve`). Compose overrides them to container names. |
| **Observability ports** (2006–2010) | `JAEGER_UI_PORT`, `OTEL_OTLP_GRPC_PORT`, `LANGFUSE_UI_PORT`, `PROMETHEUS_PORT`, `GRAFANA_PORT` | Reserved slots for services not in the default compose. |
| **Observability creds** | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_SDK_DISABLED`, `GRAFANA_ADMIN_USER/PASSWORD` | Optional — telemetry degrades gracefully if unset. |
| **App tier ports** (2011–2012) | `API_PORT`, `WEB_PORT`, `NEXT_PUBLIC_API_URL` | `NEXT_PUBLIC_API_URL` is baked into the client bundle at build time. |
| **LLM keys** | `OPENAI_API_KEY` (embeddings + eval), `GROQ_API_KEY` (primary chat), `ANTHROPIC_API_KEY` (fallback), `COHERE_API_KEY` (reranker) | See "What runs with what" below. |
| **LLM models** | `EMBEDDING_MODEL/DIM`, `GROQ_MODEL`, `OPENAI_MODEL`, `ANTHROPIC_MODEL` | Defaults are safe; change to try other tiers. |
| **Auth (Clerk)** | `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `AUTH_DEV_SECRET` | **Empty `CLERK_JWKS_URL` = dev HS256 mode** (mint local tokens). Non-empty = production RS256. |
| **Rate limits** | `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_DAY` | Per-user (Decisions 9, 20). |
| **AWS / Kill-switch** | `AWS_REGION/ACCESS/SECRET`, `GROWTHBOOK_*`, `LLM_ENABLED`, `MAX_OUTPUT_TOKENS`, `CORS_ORIGINS` | AWS is Phase-6 only. `LLM_ENABLED=false` = cost kill-switch. |

**What runs with what:**
- No keys → **unit tests only.**
- `OPENAI_API_KEY` + Docker → `/recommend` + ranking eval.
- Add an LLM key + DynamoDB (auto) → `/chat` with streaming explanations.

> **Q: The reference `.env` mentions POSTGRES_ / DATABASE_URL. Should I add those?**
> **A: No.** That's from a different project (P1, which uses Postgres+pgvector). **This project
> uses DynamoDB** for chat history (Decision 1) and **Qdrant** as the vector DB (Decision 2).
> There is no Postgres — the `POSTGRES_*` slot is intentionally absent.

## Stage 3 — Quality gates (no services needed)  `✅ VERIFIED`

```bash
make lint        # uv run ruff check . ; uv run ruff format --check .   -> All checks passed
make type        # uv run mypy packages apps tests                      -> no issues in 59 files
make test        # uv run pytest -q                                     -> integration auto-skips w/o services
```

## Stage 4 — Start data/infra (Docker)  `🐳 ✅ VERIFIED`

Bring up just the tiers you need. For the minimum happy path (Stage 5+ works), only `make db` is required:

```bash
make db                        # tier 1 — data stores only
make ps                        # verify containers running
make urls                      # print every host-side URL
```
To bring up everything at once:
```bash
make full                      # data + app + observability
```

Containers and their host ports (all sourced from `.env`; change any value there):

| Tier | Service | Host port | Container | Check |
|---|---|---|---|---|
| **data** | Qdrant (vector DB)          | **2001** | `p2-qdrant`       | http://localhost:2001/healthz → 200 |
| **data** | DynamoDB-local (history)    | **2003** | `p2-dynamodb`     | table auto-created on first API use |
| **data** | Redis (cache + rate-limit)  | **2004** | `p2-redis`        | `docker exec p2-redis redis-cli ping` → PONG |
| **obs**  | RedisInsight (Redis GUI)    | **2005** | `p2-redisinsight` | http://localhost:2005 → add host=`redis` port=`6379` |
| **obs**  | Jaeger UI (traces)          | **2006** | `p2-jaeger`       | http://localhost:2006 |
| **obs**  | Prometheus                  | **2009** | `p2-prometheus`   | http://localhost:2009 → Status → Targets |
| **obs**  | Grafana                     | **2010** | `p2-grafana`      | http://localhost:2010 → admin/admin |
| **lf**   | Langfuse (LLM traces)       | **2008** | `p2-langfuse-web` | http://localhost:2008 → login `admin@localhost` / `changeme` |
| **app**  | API                         | **2011** | `p2-api`          | http://localhost:2011/health → `{"status":"ok"}` |
| **app**  | Web                         | **2012** | `p2-web`          | http://localhost:2012 |

Langfuse's dependencies (its own Postgres, ClickHouse, Redis, MinIO) run internal-only —
no exposed ports. If you need to poke them for debugging: `docker exec -it p2-langfuse-postgres psql -U langfuse` etc.

## Stage 5 — Data ingestion (no SQL migration — schema-on-write)  `🔑 🐳 ✅ VERIFIED`

```bash
uv run python -m core.aggregate     # CSV -> data/products.json + docs/data-report.md
#   -> reviews=450 products=9 errors=0
uv run python -m retrieval.index    # embed + index into Qdrant (hybrid dense+sparse)
#   -> indexed 9 products into Qdrant (hybrid dense+sparse)
```
The DynamoDB table is auto-created (`ensure_table`) on first API use; no migrations.

## Stage 6 — Run a query / get a result without the server  `🔑 🐳 ✅ VERIFIED`

```bash
uv run python -m evaluation.ranking.run    # real retrieve->rank over the golden set
#   hybrid only : NDCG@3=0.8022  MRR=0.8333  Recall@3=0.8187   (+reranker A/B; reranker gated OFF)
```

## Stage 7 — Run the backend API  `🔑 🐳 ✅ VERIFIED`

```bash
make serve                                # uses ${API_PORT:-2011} — reads .env
curl http://localhost:2011/health         # {"status":"ok"}
curl http://localhost:2011/metrics        # prometheus text (http_requests_total, cache_*_total)
```

To run on a different port for a single run:
```bash
API_PORT=2999 make serve                  # override for one invocation
```

## Stage 8 — Exercise every cross-cutting concern  `✅ VERIFIED (live)`

Mint a dev token (dev HS256 mode; works because `CLERK_JWKS_URL` is empty):
```powershell
$tok = (uv run python -c "from core.auth import mint_dev_token; print(mint_dev_token('demo'))").Trim()
$h = @{ Authorization = "Bearer $tok" }
```

- **Auth** — no token is rejected before any service is touched:
  ```powershell
  Invoke-WebRequest http://localhost:2011/recommend -Method POST -Body '{"query":"x","k":3}' -ContentType application/json -SkipHttpErrorCheck   # 401
  ```
- **Recommend (ranking-only, fast):**
  ```powershell
  Invoke-RestMethod http://localhost:2011/recommend -Method POST -Headers $h -Body '{"query":"cheap neckband for the gym","k":3}' -ContentType application/json
  #   top -> "U&I Titanic Series - Low Price ... Neckband" (final_score 0.855)
  ```
- **Chat (SSE: cards first, then streamed tokens):**
  ```powershell
  (Invoke-WebRequest http://localhost:2011/chat -Method POST -Headers $h -Body '{"query":"good bass headphones","session_id":"s1","k":2}' -ContentType application/json).Content
  #   events observed: recommendations x1, token x117, done x1
  ```
- **Rate limiting / quotas** — 30/min, 500/day per user → `429` + `Retry-After` once exceeded
  (loop `/recommend` > 30× in a minute). Unit-tested in `tests/unit/test_ratelimit.py`.
- **Caching** — call `/recommend` twice with the same query, then:
  ```powershell
  (Invoke-WebRequest http://localhost:2011/metrics -Headers $h).Content | Select-String cache_hits_total
  #   cache_hits_total{layer="response"} increments on the 2nd identical call
  ```
- **Observability** — open **Jaeger** http://localhost:2006 (service `p2-recommender`, span
  `recommend.pipeline`). LLM token/cost traces appear in **Langfuse** if its keys are set.
- **Security** — query is logged via PII redaction (`redact_pii`); the LLM can only write *reasons*
  (product set fixed by ranking) so injected review text can't add/swap products
  (`tests/unit/test_security.py`).
- **Cost controls + KILL-SWITCH** — set `LLM_ENABLED=false` in `.env`, restart the API; `/chat`
  returns the recommendation cards + a `degraded` done event with **no token stream** (no LLM spend).
  `/recommend` is unaffected. (Verified by `tests/integration/test_killswitch.py`.)
- **Circuit breakers / graceful degradation** — chaos drill:
  ```bash
  docker compose -f infra/compose/docker-compose.data.yml stop qdrant
  #   /recommend still returns 200 -> popularity-only ranking (rating x volume); breaker opens
  docker compose -f infra/compose/docker-compose.data.yml start qdrant   # recovers
  #   stop redis -> still serves (cache bypassed, rate-limit fails open). (tests/unit/test_resilience.py)
  ```
- **GDPR — RTBF + DSAR:**
  ```powershell
  Invoke-RestMethod http://localhost:2011/account/export -Headers $h          # DSAR -> {user_messages:[...]}
  Invoke-RestMethod http://localhost:2011/account -Method DELETE -Headers $h  # RTBF -> {deleted: 2}
  Invoke-RestMethod "http://localhost:2011/history?session_id=s1" -Method DELETE -Headers $h
  ```

## Stage 9 — Frontend (Next.js)  `✅ VERIFIED (build)`

```bash
cd apps/web
npm install
# Windows &-path: call binaries via node; otherwise `npm run typecheck` / `npm run build` work:
node node_modules/typescript/bin/tsc --noEmit      # type-check (no errors)
node node_modules/next/dist/bin/next build         # -> "Compiled successfully"
```
Run it against the API (visual check is yours):
```bash
# apps/web/.env.local (already points at the API on 2011):
#   NEXT_PUBLIC_API_URL=http://localhost:2011
#   NEXT_PUBLIC_DEV_TOKEN=<uv run python -c "from core.auth import mint_dev_token; print(mint_dev_token('web'))">
PORT=2012 node node_modules/next/dist/bin/next dev            # http://localhost:2012
```
Type a query → **cards appear first**, then the explanation **streams token-by-token**; "Stop" cancels.

## Stage 10 — Eval gate / run CI locally  `🔑 🐳 ✅ VERIFIED`

```bash
uv run pytest -q -m "not integration"     # CI job 1 (unit)
uv run pytest -q -m integration           # CI job 2 (needs services+key)  -> 9 passed
uv run python -m evaluation.ranking.gate  # CI job 3 -> eval-gate: PASS (exit 0); blocks on regression
```

## Stage 11 — Docker images / full stack  `🐳 ✅ VERIFIED (api image + run)`

```bash
docker build -f apps/api/Dockerfile -t p2-api .        # multi-stage, non-root; builds
docker run --rm -p 2011:2011 p2-api                    # curl /health -> {"status":"ok"}
# whole stack in one command (needs .env at repo root):
make full                                              # api:2011  web:2012  qdrant:2001  redis:2004  dynamodb:2003  jaeger:2006  prom:2009  grafana:2010  redisinsight:2005
```

## Stage 12 — Kubernetes (Helm)  `✅ VERIFIED (lint + render)` · deploy `☁️`

```bash
helm lint ops/helm/p2-recommender                 # 1 chart linted, 0 failed
helm template p2 ops/helm/p2-recommender          # renders 3 Deployments, 4 Services, StatefulSet, HPA, SA
helm template p2 ops/helm/p2-recommender | kubectl apply --dry-run=client -f -
# deploy to a real/local cluster (kind/minikube or EKS):
helm install p2 ops/helm/p2-recommender -n p2 --create-namespace
```

## Stage 13 — Terraform (AWS IaC)  `✅ VERIFIED (fmt + init + validate)` · plan/apply `☁️`

```bash
cd infra/terraform
terraform fmt -check -recursive      # OK (all formatted)
terraform init -backend=false        # downloads aws provider + community vpc/eks modules
terraform validate                   # -> "Success! The configuration is valid."
# against a real account (NO apply yet — Phase 6 gate):
terraform init && terraform plan -out tfplan
```

## Stage 14 — CI/CD (GitHub Actions)  `✅ VERIFIED (YAML + jobs run locally)` · live run on push

- `.github/workflows/ci.yml` (on push/PR): **lint-type-test** (+ pip-audit + bandit) → **image-scan**
  (Trivy) → **integration** (qdrant/redis/dynamodb service containers) → **eval-gate**.
- `.github/workflows/cd.yml` (on `v*` tag): OIDC→AWS, build+push api/web to **ECR**, Helm deploy.
- **Required repo secrets:** `OPENAI_API_KEY`, `GROQ_API_KEY`, `AWS_DEPLOY_ROLE_ARN` (OIDC),
  `ECR_REGISTRY`.
- Run a workflow locally with [`act`](https://github.com/nektos/act), or just run each job's commands
  (Stage 10 is exactly the CI job sequence).

> **Note:** The CI workflow uses standard image ports (`6333:6333`, etc.) for GitHub Actions
> service containers because those ports only exist on the CI runner — they never conflict with
> your local machine, and the runner starts clean each time. That is intentional; do not change
> them to 2000-range unless you also add `--env-file`-style overrides to every step.

---

## Langfuse (LLM tracing) — first-boot notes

`make langfuse` starts 6 containers (web + worker + postgres + clickhouse + redis + minio).
**Cold start is ~1–3 minutes** — ClickHouse warm-up + Langfuse Prisma migrations dominate.
Watch progress:
```bash
docker logs -f p2-langfuse-web                  # look for "Ready in ..."
curl -sf http://localhost:2008/api/public/health  # 200 with {"status":"OK",...} = ready
```

On the very first boot with an empty postgres volume, Langfuse auto-provisions via
`LANGFUSE_INIT_*`:
- Org `p2-recommender`
- Project `local`
- Admin user (email/password from `.env` — default **`admin@example.com`** / `changeme`)
- **Registers `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` from `.env` as project API keys** —
  so the api container's traces flow straight to your local instance with the same keys you
  already had. No manual key rotation needed.

Verify the bootstrap:
```bash
source .env
curl -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" http://localhost:2008/api/public/projects
# → 200 { "data": [ { "id": "p2-recommender-project", "name": "local", ... } ] }
```

The API container sees Langfuse at `http://langfuse-web:3000` (container DNS, overridden in
`docker-compose.app.yml`). If the langfuse tier isn't up, the Langfuse SDK degrades silently
— no error surfaced to `/chat` callers.

**Re-init after wipe:** if you `make downv`, the postgres volume is destroyed and the init
runs again on next boot with whatever `.env` says at that time. That's the only time the
`LANGFUSE_INIT_*` values are honoured — subsequent boots leave org/project/keys/user alone.

**Alt: Langfuse Cloud.** If you'd rather not run 6 containers, sign up at langfuse.com, paste
the cloud pk/sk into `.env`, set `LANGFUSE_HOST=https://cloud.langfuse.com` (or the EU/US
variant), and skip `make langfuse`. The api sends traces to cloud instead.

### Two gotchas we hit setting this up

1. `LANGFUSE_INIT_USER_EMAIL` must have a real TLD — Langfuse's zod validator rejects
   `@localhost`. Use `admin@example.com` or your own real address.
2. The ClickHouse healthcheck must probe `127.0.0.1:8123`, not `localhost:8123`. Alpine's
   BusyBox resolver returns `::1` first, but ClickHouse only binds IPv4 → "connection
   refused" even though the server is listening. Fixed in `docker-compose.langfuse.yml`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `'...node_modules\.bin\' is not recognized` / `Cannot find module 'D:\next...'` | the `&` in the path breaks npm shims — run `node node_modules/<tool>/...` directly, or clone to a path without `&`/spaces |
| `VIRTUAL_ENV ... does not match .venv` warning | harmless; uv uses `.venv` |
| `No module named 'core'` running a script | use `uv run python -m <pkg.module>`; for the API use `--app-dir apps`; for ad-hoc scripts set `PYTHONPATH=apps` when importing `api.*` |
| integration tests skipped | start Docker services + set `OPENAI_API_KEY`; they skip by design otherwise |
| `/chat` 401 with a dev token | `CLERK_JWKS_URL` is set in `.env` → it expects real Clerk tokens; empty it for dev HS256 |
| port 2011/2012 busy | change `API_PORT` / `WEB_PORT` in `.env` (and re-run `make up`) — nothing else needs editing |
| compose says `QDRANT_HTTP_PORT variable is not set` | ensure `.env` is at the repo root; compose auto-loads it from CWD when you use `make db/app/obs/full` |
| Trying old ports (6333, 8080…) from a stale terminal | the stack has been renumbered to the 2000-range; re-open your shell, re-source `.env`, and run `make urls` |
| Old `make up` runs the wrong stack | `make up` is now an alias for `make full` (db+app+obs). Use `make db` / `make app` / `make obs` for tier-only |
| `make` not found (Windows) | run the raw `uv run ...` shown beside each `make` target |

## Related docs
[decision-log.md](decision-log.md) · [transformation-plan.md](transformation-plan.md) ·
[how-to-verify.md](how-to-verify.md) (per-step) · [hardening.md](hardening.md) ·
[runbook.md](runbook.md) (incidents) · [portfolio-writeup.md](portfolio-writeup.md).
