# Verify P2: every component, by browser and by CLI

This guide checks that every part of P2 works, from the web page down to the databases, and that
each check would catch a real failure. Every component has a browser check, a CLI check, what
"working" looks like, and what "broken" looks like.

Commands are given for **PowerShell** (the default on this machine). Where Git Bash differs, both
are shown. Ports are the defaults from `.env`. `make urls` prints the ones in effect, and
`make service_ls` prints the logins.

## 0. Bring it up, then the 10-second check

```powershell
make up            # compose (21 containers) + the kind cluster; ends with the URL directory
make verify        # 36 checks, read-only, a few seconds; exit code 1 if anything FAILs
make verify LIVE=1 # + one tiny call per LLM provider and SerpApi's free account endpoint
```

`make verify` statuses:

| Status | Meaning |
|---|---|
| PASS | Works, and the check proved it end to end (e.g. a login, not just an open port). |
| WARN | Works, but there is nothing to show yet (no traces before the first chat), or works with a caveat (a provider failing over). |
| FAIL | Broken. The detail says what was expected and what came back. |
| SKIP | Not checked: kind not running, or a LIVE-only check without `LIVE=1`. |

`make verify` checks the plumbing. The browser walk in section 1 checks what a user sees. Do both:
each catches failures the other misses.

## 1. The user's path: one question, followed everywhere

This is the most important check. One real question passes through every layer, and you then
find its footprint in each tool.

1. Open http://localhost:2012 and click **Sign in**. Sign in with your Clerk account.
   *Working:* you land on `/dashboard`. *Broken:* the Clerk widget never loads (wrong
   `CLERK_PUBLISHABLE_KEY` baked into the web image: fix `.env`, then `make up`), or you loop back
   to sign-in (`CLERK_SECRET_KEY` wrong).
2. Open **Discover** and ask: `wireless earbuds with good battery under $100`.
   *Working:* product cards appear first (~1–2 s, live Google Shopping offers through SerpApi), then
   a short reason under each card fills in (the LLM). *Broken:* "source unavailable" means the
   SerpApi key is missing or out of searches. Cards without reasons means every LLM rung failed.
3. Ask **the same question again**. *Working:* instant: it came from the Redis cache, and SerpApi
   spent nothing (check in step 6).
4. DevTools (F12) → **Network** → the `aggregate/stream` request:
   - Request headers: `Authorization: Bearer eyJ…`, a Clerk session token.
   - Response: `text/event-stream`: an `offers` event (the cards), a `final` event (cards +
     reasons), then `done`. A cached answer skips straight to `final`.
5. **Grafana** http://localhost:2010 → *P2 - API & LLM*. *Requests/s by endpoint* shows
   `/aggregate/stream`. *LLM calls by provider* shows which LLM answered. *LLM tokens* and
   *SerpApi searches* moved.
6. **RedisInsight** http://localhost:2005 → *p2-redis (app cache)* → Browser. You should see an
   `agg:…` key (the cached answer) and `serpapi:spend:day:<today>` / `serpapi:spend:month:<month>`
   (the budget counters). The second ask didn't increment them.
7. **Langfuse** http://localhost:2019 (signs you in) → *Tracing*. The newest trace has a
   generation with the **model** (e.g. `gpt-4o`), input/output **tokens** and **cost**.
8. **Jaeger** http://localhost:2006 → Service `p2-recommender` → *Find Traces*. The
   `POST /aggregate/stream` trace shows the request's spans and timings.

If all eight hold, the app works end to end: auth → API → SerpApi → ranking → LLM → cache →
metrics → traces.

## 2. Frontend (Next.js, :2012)

| | |
|---|---|
| Browser | http://localhost:2012 renders the landing page; `/sign-in` renders Clerk's widget; `/dashboard` without signing in redirects to sign-in. |
| CLI | `curl.exe -s -o NUL -w "%{http_code}" http://localhost:2012/` → `200` (Git Bash: `-o /dev/null`) |
| Logs | `docker logs p2-web --tail 50` |
| Broken looks like | 500 on every page (missing `CLERK_SECRET_KEY`); a blank page with console errors about the publishable key (rebuild: `make up`). |

## 3. Backend API (FastAPI, :2011)

| Check | Command | Working |
|---|---|---|
| Health | `curl.exe http://localhost:2011/health` | `{"status":"ok"}` |
| Docs | http://localhost:2011/docs | Swagger lists 9 routes |
| Fails closed | `curl.exe -s -o NUL -w "%{http_code}" -X POST http://localhost:2011/recommend -H "Content-Type: application/json" -d '{"query":"headphones"}'` | `401`: no token, no answer |
| Metrics | `curl.exe -s http://localhost:2011/metrics \| Select-String llm_requests_total` | per-provider counters |
| Logs | `docker logs p2-api --tail 100` | one line per request; `LLM call failed provider=…` when a rung fails |

**An authenticated call from the CLI.** The API accepts only Clerk tokens (`CLERK_JWKS_URL` is
set). Copy a token from the browser: DevTools → Network → any API request → Request headers →
`Authorization` (without `Bearer `). It expires after ~60 s, so be quick:

```powershell
$t = "<paste the token>"
curl.exe -s -X POST http://localhost:2011/recommend -H "Authorization: Bearer $t" `
  -H "Content-Type: application/json" -d '{"query":"good bass headphones","k":3}'
```

(PowerShell 7: JSON in single quotes, as above. Git Bash: the same, with `\` instead of `` ` ``.)

*Working:* 3 products from the static catalog, each with a rating and a reason. A 401 here means
the token expired: copy a fresh one.

## 4. Data stores

### Qdrant: catalog vectors (:2001)

- **Browser:** http://localhost:2001/dashboard. It asks for the API key once: `make service_ls` →
  Qdrant → api key. Collections → `products` → 9 points. Open one: a dense vector (1536 dims), a
  BM25 sparse vector (`langchain-sparse`), and the payload: the review text plus `product_id`,
  `title`, `avg_rating`, `review_count`.
- **CLI:**
  ```powershell
  $k = (uv run python -c "from dotenv import get_key; print(get_key('.env','QDRANT_API_KEY'))")
  curl.exe -s http://localhost:2001/collections/products -H "api-key: $k"   # points_count: 9, status green
  curl.exe -s -o NUL -w "%{http_code}" http://localhost:2001/collections     # 401 without the key
  ```
- **Broken:** `points_count: 0` or 404 → `make seed`.

### DynamoDB local: chat history (:2003)

- No browser UI. Use the AWS CLI or NoSQL Workbench (any credentials work: it runs `-sharedDb`).
- **CLI:**
  ```powershell
  $env:AWS_ACCESS_KEY_ID="local"; $env:AWS_SECRET_ACCESS_KEY="local"
  aws dynamodb list-tables --endpoint-url http://localhost:2003 --region us-east-1
  aws dynamodb scan --table-name p2-recommender --endpoint-url http://localhost:2003 --region us-east-1 --max-items 3
  ```
  Without the AWS CLI: `uv run python -c "import boto3; c=boto3.client('dynamodb',endpoint_url='http://localhost:2003',region_name='us-east-1',aws_access_key_id='local',aws_secret_access_key='local'); print(c.list_tables())"`
- Items are `PK=USER#<id>`, `SK=SESSION#<id>#MSG#<time>`. `/chat` writes them, so the table appears
  after the first chat. It runs **in memory**: a container restart empties it, by design.

### Redis: app cache (:2004)

- **Browser:** RedisInsight → *p2-redis (app cache)*. Keys: `agg:*` (aggregator answers),
  `resp:*` (catalog answers), `emb:*` (query embeddings), `serpapi:spend:*` (budget),
  `catalog:version`, plus rate-limit counters.
- **CLI:** `docker exec -it p2-redis redis-cli` then `DBSIZE`, `KEYS serpapi:*`,
  `GET serpapi:spend:month:<yyyy-mm>`.
- **Persistence:** AOF on a volume. `make down`, then `make up`: the keys are still there.

## 5. Observability

### Grafana (:2010): no login

Open http://localhost:2010. The home dashboard is **P2 - Service health**. Check:

- **Services:** every tile `UP` (blackbox probes every 15 s). A red tile names the dead service.
- **Metrics endpoints scraped:** every tile `UP`.
- **Firing alerts:** `0`. If not, Prometheus → Alerts shows which.
- **Dashboards (folder P2):** *API & LLM* (traffic, errors, latency, LLM calls, tokens, cache,
  SerpApi), *Data stores* (Redis ×2, Postgres, ClickHouse, MinIO, Qdrant), *Containers* (CPU and
  memory per container, from cAdvisor), *Overview*.
- **Explore → Jaeger:** search traces without leaving Grafana.
- **Broken:** "No data" on a panel *after* you've used the app means a broken query or scrape.
  Before the first request some panels are legitimately empty. `make verify` runs every panel's
  query and lists the empty ones.

### Prometheus (:2009)

- http://localhost:2009/targets: every target `UP` (the API, Qdrant, both Redis exporters,
  Postgres, ClickHouse, MinIO, Grafana, Jaeger, cAdvisor, Prometheus itself, 16 probes).
- http://localhost:2009/alerts: 11 rules, normally all *Inactive*.
- Query: `sum by (provider, status) (increase(llm_requests_total[1h]))` shows which LLM rungs
  answered and which failed.
- **Prove an alert fires:** `docker stop p2-api`, wait 2–3 min: `ApiDown` goes *Pending* then
  *Firing*, and the Service health dashboard turns red. Then `docker start p2-api`.

### Jaeger (:2006)

Service `p2-recommender` → *Find Traces*. One trace per request; `/aggregate/stream` and `/chat`
traces show where the time went. No `p2-recommender` service means the API can't reach
`jaeger:4317`: `docker logs p2-api` and `docker logs p2-jaeger`.

### Langfuse (:2019 → :2008)

- http://localhost:2019 signs you in (the session cookie is set by a small proxy; no form) and opens
  *Tracing* of `p2-recommender-project`. Typing the login also works, from `make service_ls`.
- A trace → its **generation**: model, prompt, completion, tokens, latency, cost.
- **CLI** (project keys from `make service_ls`):
  ```powershell
  curl.exe -s -u "<public key>:<secret key>" "http://localhost:2008/api/public/traces?limit=1"
  ```
- **Broken:** traces never appear → `docker logs p2-langfuse-worker` (ingestion) and check the
  API has `LANGFUSE_*` keys (`docker exec p2-api env | Select-String LANGFUSE_HOST`).

### RedisInsight (:2005)

Both databases are listed without adding anything: *p2-redis (app cache)* and *p2-langfuse-redis
(Langfuse queue)*. Click each: it connects (the Langfuse one uses its password from `.env`).

### cAdvisor (:2020)

http://localhost:2020/containers/: live CPU/memory per container. The same data is graphed in
Grafana → *P2 - Containers*.

## 6. Langfuse's own stores

### Postgres (pgAdmin)

`make service_ls` → *Postgres (Langfuse)* gives everything pgAdmin needs. In pgAdmin:
**Register → Server**, *General* name `p2-langfuse`, *Connection* host `localhost`, port `2013`,
maintenance database `langfuse`, username and password from `service_ls`. Then *Databases →
langfuse → Schemas → public → Tables*: `projects`, `users`, `api_keys`, `organizations`, …
(Langfuse's metadata; traces are in ClickHouse).

CLI: `docker exec -it p2-langfuse-postgres psql -U langfuse -d langfuse -c "select id, name from projects;"`

P2's own data isn't in Postgres (chats → DynamoDB, catalog → Qdrant, caches → Redis). This is
the only Postgres in the stack.

### ClickHouse

http://localhost:2014/play, with user/password from `service_ls`. Run:
`SELECT name, count() FROM traces GROUP BY name ORDER BY 2 DESC`
CLI: `docker exec -it p2-langfuse-clickhouse clickhouse-client --user langfuse --password <pw> -q "SELECT count() FROM traces"`

### Redis (Langfuse queue, :2016)

RedisInsight → *p2-langfuse-redis*, or
`docker exec -it p2-langfuse-redis redis-cli -a <password> --no-auth-warning DBSIZE`.

### MinIO

http://localhost:2018, with user/password from `service_ls` → bucket `langfuse`: raw ingestion
events and media, one object per event.

## 7. LLMs and models

P2 runs no local GPU engine (no vLLM/SGLang). The LLMs are hosted and tried in order:

| Rung | Model (from `.env`) | Check |
|---|---|---|
| 1. Groq | `GROQ_MODEL` | `make verify LIVE=1` → `groq PASS` |
| 2. OpenAI | `OPENAI_MODEL`; embeddings `EMBEDDING_MODEL` | `openai chat PASS`, `openai embeddings PASS` |
| 3. Anthropic | `ANTHROPIC_MODEL` | `anthropic PASS` |
| SerpApi | Google Shopping | `serpapi account PASS` + searches left this month (free call) |
| Local, CPU | fastembed `Qdrant/bm25` (hybrid search, inside the API) | qdrant points carry a sparse vector |

**Which rung actually answered:** Grafana → *API & LLM* → *LLM calls by provider* / *LLM failure %*,
or a Langfuse generation's `model`. A dead key doesn't break the app: the next rung answers. But
it costs more, so it's alerted: `LLMProviderFailing` fires when a provider fails >50% of ≥3 calls
for 5 min.

## 8. Kubernetes (kind)

`make up` starts it (`make kind-status` shows nodes, pods and whether the deployed image is your
current code).

| Check | Command | Working |
|---|---|---|
| Nodes | `kubectl --context kind-p2 get nodes` | 3 nodes `Ready` |
| Pods | `kubectl --context kind-p2 -n p2 get pods` | api ×2, web ×2, qdrant-0, redis-0, dynamodb: 7 pods `Running` (the seed Job is deleted once it succeeds) |
| Web | http://app.localhost | the same web app, signed in with the same Clerk account |
| API | `curl.exe http://app.localhost/api/health` | `{"status":"ok"}` (the Gateway strips `/api`) |
| HTTPS | `curl.exe -k https://app.localhost/api/health` | `200` (local CA from cert-manager; `-k` skips trusting it) |
| Smoke | `make kind-smoke` | every step `ok` |
| Logs | `kubectl --context kind-p2 -n p2 logs deploy/api --tail 50` | |
| Data | `kubectl --context kind-p2 -n p2 port-forward svc/qdrant 6333:6333` → http://localhost:6333/dashboard | 9 points |

Python and .NET don't resolve `*.localhost`; browsers and curl.exe do.

**Resilience in 1 minute:** delete one of the two api pods while the app is in use:

```powershell
$pod = kubectl --context kind-p2 -n p2 get pod -l app.kubernetes.io/component=api -o name | Select-Object -First 1
kubectl --context kind-p2 -n p2 delete $pod --wait=false
kubectl --context kind-p2 -n p2 get pods -w      # a replacement is Ready in ~30 s
```

http://app.localhost keeps answering throughout: the other replica serves (Phase 6 drill under
load: 901/901 requests OK). Deleting *both* at once is an outage, not a drill: the
PodDisruptionBudget limits evictions such as node drains, not direct deletes.

## 9. Lifecycle checks

| Do | Expect |
|---|---|
| `make down` then `make up` | Qdrant still has 9 points, Redis keys survive, Langfuse traces survive; kind nodes restart and the app answers again (`make verify` all PASS). |
| `make upv` | Everything wiped and rebuilt from zero, catalog re-seeded, a new kind cluster (~15 min). |
| `make up KIND=0` | Compose only; kind left alone. |
| Low memory | With another kind cluster running and < 6 GB free, `make up` skips kind and names that cluster. |

## Verify-yourself checklist

- [ ] `make verify` → 0 FAIL
- [ ] `make verify LIVE=1` → every provider you have a key for PASSes (an expired key FAILs and says so)
- [ ] Section 1: sign in, ask, see cards then reasons; ask again, instant
- [ ] The same question visible in Grafana, RedisInsight, Langfuse (model + cost) and Jaeger
- [ ] Grafana opened with no login; Langfuse opened through :2019 with no login; RedisInsight shows both DBs
- [ ] pgAdmin connects to Langfuse Postgres with the `service_ls` logins; MinIO console login works
- [ ] `docker stop p2-api` → `ApiDown` fires within ~3 min → `docker start p2-api` → resolves
- [ ] http://app.localhost works and `make kind-smoke` passes
- [ ] `make down` → `make up` → data still there
