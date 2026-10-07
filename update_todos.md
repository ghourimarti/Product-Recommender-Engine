# Update TODOs: P2 ProductIQ (Enterprise2)

> **As of:** 2026-10-07 · **HEAD:** `56b28de` · branch `main` · 62 commits · 🆕 Phase 6 built and verified (6A–6I); waiting on you: Clerk sign-in, 9 commits + push, first CI run
> **How this was built:** I checked every status below against the repo today: code, `ci.yml`,
> `git log`, a live `pytest --collect-only`, and the reports in `Document/docs/`. When a doc and
> the code disagree, the code wins, and the mismatch goes in **§10 Drift & bugs**. Vendor prices and
> credits were checked on 2026-10-06; they change often, so re-check before spending.
> 🆕 **Updated 2026-10-06/07 (Phase 6 session):** progress on 6A–6E, three Phase 6 decisions,
> new findings, and status marks instead of checkboxes. Items added or changed in that session
> are marked 🆕.
> **This file is local-only:** `Document/` is gitignored.

### Phase map (revised 2026-10-06)

| # | Phase | Cost |
|---|---|---|
| 0–5 | Recon → requirements → decisions → plan → build → hardening | done / mostly done |
| **6** | **Deployment using kind** (local, multi-node, production-like practice) | **$0** |
| **7** | **Non-AWS real managed Kubernetes: DigitalOcean DOKS** (NEW) | ~$15–40 if torn down between sessions |
| **8** | **Deployment on AWS: EKS** | ~$0.25–0.35/hour while up |
| **9** | **Portfolio writeup** (was Phase 7) | $0 |
| App. A | Scale guide: 10k → 100k → 1M → 10M+ users | reference |
| App. B | Kubernetes vendors + free credits | reference |

### Legend

Every item starts with exactly one **status**:

| Mark | Meaning |
|---|---|
| ✅ | Done and verified (command run, or evidence in the repo) |
| 🔄 | In progress, or partly done |
| ⏳ | Pending: not started |
| ⏸️ | Deferred on purpose (reason given) |

A status can be followed by a **note**:

| Mark | Meaning |
|---|---|
| 🔁 | Built differently from the plan (the deviation is noted) |
| ✂️ | In the plan but never built |
| 🆕 | Added or changed in the 2026-10-06/07 Phase 6 session |

---

## 0. Where things stand

| Phase | Status | Summary |
|---|---|---|
| 0 Recon | ✅ | Demo inventoried, defects named |
| 1 Requirements | ✅ | F1–F7 + NFRs defined. NFR status re-measured in §1.3 |
| 2 Decision log | 🔄 | D1–D24 written. **Some picked options were never built** (§2.4) |
| 3 Plan | ✅ | Batches A–F, Steps 1–18, risk register |
| 4 Execution (Steps 1–18 + 5b) | ✅ / 🔁 | All 19 steps shipped. Several sub-items descoped (✂️ list in §4) |
| 4A Aggregator pivot (A1–A7) | ✅ | Live SerpApi path is the product. Eval set is only 4 fixtures |
| 4B Inspection → remediation | 🔄 | 27 findings: 26 fixed, **M-12 partial** |
| 4C Honesty / cleanup pass | ✅ | Jul 28 – Aug 8 commits |
| 5 Hardening | 🔄 | Audits done. **Trivy, bandit-in-CI and ESO are claimed but not real** (§5) |
| **6 kind** | 🔄 | 🆕 6.1 ✅ · 6A cluster ✅ · 6B chart structure ✅ · 6C chart hardening ✅ · 6D per-env wiring ✅ · 6E add-ons + first deploy 🔄 (browser sign-in pending) · 6F monitoring ✅ · 6G GitOps ✅ (Argo CD manages p2) · 6H drills ✅ (8/8) · 6I CI + evidence ✅ (CI's first GitHub run pending your push) · nothing committed yet. `make kind-all` from zero: 595 s. First install 2026-10-07: release `p2` deployed; smoke 7/7 (devauth) and 4/4 (clerk) |
| **7 DigitalOcean DOKS** | ⏳ | New. Blocked on decision 7.0 (credit status, history store) |
| **8 AWS EKS** | 🔄 | Terraform validates and a `tfplan` exists. **Never applied; `cd.yml` has 0 runs** |
| **9 Portfolio** | 🔄 | Writeup exists but is **pre-pivot** (says 83 tests, no aggregator) |
| Drift & bugs found today | ⏳ | 🆕 15 items (11 + 4 found in the Phase 6 session), mostly cheap and offline (§10) |
| Roadmap | ⏳ | 9 items (§11) |

## 0.1 Do next (priority order)

1. 🆕 **Sign in with Clerk** at http://app.localhost and run one search (the cluster is up, clerk profile).
2. 🆕 **Commit Phase 6 as nine commits:** `pwsh -File Document\phase6-snapshots\commit_phase6.ps1` (rehearsed
   on a clone: 9 commits, no trailers, tree unchanged). ⚠️ Not the older 4- or 5-commit sequences.
   Then push `origin` and `mirror`, and watch the new `kind` workflow's first run.
3. 🆕 **When done with the cluster:** `make kind-down` (frees ~5.7 GB of the Docker VM).
4. **§10 drift fixes.** One sitting, offline, $0 (🆕 now 15 items).
5. **Add Trivy + bandit to CI (§5).** `hardening.md` says CI runs them. It doesn't.
6. **Decision 7.0.** Check whether your DO credit still exists (it probably doesn't). Pick a budget or vendor.
7. **Phase 7: DOKS.** First real cluster: real load balancer, storage, DNS, TLS, GitOps, alerting, backups.
8. **R2 E2E tests + R3 LangChain/Langfuse upgrade (§11).** R3 may be needed before 7.0.6.
9. **Phase 8: EKS.** Same chart, AWS-native extras (IRSA / Pod Identity, ALB, Secrets Manager).
10. **Phase 9: portfolio.** Draft now; add evidence after each deployment phase.

---

## Phase 0: Recon ✅

- ✅ 0.1 Inventory `demo/`: Flask app, LangChain chain, AstraDB vector store, 450-review Flipkart CSV.
- ✅ 0.2 Name the defects:
  - ✅ All users share one in-memory conversation (cross-user leakage, lost on restart).
  - ✅ Flask dev server on the "production" path.
  - ✅ Prometheus counter counts page loads, not inferences.
  - ✅ No tests, eval, auth, IaC, rate limit or caching.
  - ✅ `rating` / `summary` columns thrown away.
- ✅ 0.3 Spot the unused signal (rating) and reframe the demo as a **rating-aware recommender**.
- Evidence: the "The problem" section of `portfolio-writeup.md`.

## Phase 1: Requirements ✅

- ✅ 1.1 Functional requirements F1–F7:
  - F1 conversational recommendation · F2 rating-aware ranking · F3 grounded explanations + citations
  - F4 per-user conversational memory · F5 ingestion pipeline · F6 "no good match" state · F7 admin/eval surface
- ✅ 1.2 Non-functional requirements: p95 latency, cache ≥ 60%, < $0.005/query, 200 RPS, 1M MAU,
  99.9% uptime, GDPR deletion / DSAR / 90-day retention, no PII leakage.
- ✅ 1.3 Re-measured during inspection and remediation. Status now:

| Requirement | Target | Latest evidence | Status |
|---|---|---|---|
| F1 Recommendation | — | `/aggregate` returns ranked live offers | ✅ |
| F2 Rating-aware ranking | — | Blend visible in `final_score` | ✅ |
| F3 Grounded explanations | — | Google Shopping gives rating / count / snippet, **not review text** | 🔄 Weaker than the "grounded in real reviews" claim |
| F4 Per-user memory | — | DynamoDB, IDOR test passes | ✅ |
| F5 Ingestion | — | `core.aggregate` + `retrieval.index` | ✅ |
| F6 No-match state | — | Absolute cosine floor 0.30 (M-1). `source_unavailable` ≠ `no_match` (C-4) | ✅ |
| F7 Eval surface | — | Aggregator gate on the shipped path (M-7) | ✅ |
| p95 ranking-only, cached | < 300 ms | 7.59 ms (k6, 50 VUs, laptop) | ✅ local · ⏳ on a real cluster (7.6) |
| p95 `/recommend` uncached | < 2 s | 808 ms | ✅ |
| p95 `/aggregate` cold | < 2 s | ~2.94 s. Cards now arrive ~2.6 s before the answer, but SerpApi itself takes ~2–3 s | 🔄 Not met for cold. A code change can't fix this |
| Cache hit rate | ≥ 60% | 66.8% (inflated by repeated test queries) | ✅ (caveat) |
| Cost / query | < $0.005 | `stream_usage=True` landed (M-3). **Never re-confirmed with a live Langfuse trace** | ⏳ Verify in 7.5 |
| 200 RPS / 1M MAU / 99.9% | — | Never load-tested on the real path. SerpApi caps it at 250/month (see App. A) | ⚪ Not verifiable without a paid data source |
| GDPR deletion / DSAR | required | `DELETE /account`, `GET /account/export` | ✅ |
| GDPR 90-day retention | required | `ttl` attribute written on every item (M-11) | ✅ code · ⏳ live TTL check (7.5 / 8.2) |
| No PII leakage | required | `clean_user_text` at the API edge (M-4) | ✅ |

## Phase 2: Decision log 🔄

- ✅ 2.1 D1–D24 written (`Document/docs/decision-log.md`; the tracked copy is `docs/decision-log.md`).
- ✅ 2.2 At-a-glance table: serial number, options, pick, reason, production-grade?, gap filled.
- ✅ 2.3 Your changes applied: **D1** DynamoDB · **D2** Qdrant · **D5** OpenAI `text-embedding-3-small` @1536
  · **D6** full LangChain · **D15** EKS · **D19** ranking gate + RAGAS + promptfoo + GrowthBook.
- 🔄 2.4 **Reconcile the log with what was actually built.** Add an "Outcome" column so the log doesn't over-claim:

| Decision | Picked | Built | Mark | Where it can close |
|---|---|---|---|---|
| D19 eval | RAGAS library | Custom LLM-judge (RAGAS hard-imports a removed `langchain_community` module) | 🔁 | — |
| D19 eval | promptfoo | Not built | ✂️ | Optional |
| D19 / D20 flags | GrowthBook (`llm_enabled`) | `LLM_ENABLED` env var | 🔁 | App. A (10M tier) |
| D19 judge | Off-family (Claude) | OpenAI gpt-4o (no Anthropic key). Off the *primary* Groq model, not off-family | 🔁 | — |
| D13 traces | Tempo | Jaeger | 🔁 | 6.5 / 7.3 |
| D15 images | Distroless | `python:3.12-slim` multi-stage, non-root (api ~725–774 MB) | 🔁 | M-12 / R9 |
| D15 platform | EKS only | **kind → DOKS → EKS** (revised 2026-10-06) | 🔁 | Phases 6–8 |
| D15 workers | ARQ worker + KEDA | Not built | ✂️ | Optional |
| D16 CD | ArgoCD + Argo Rollouts canary | `helm upgrade --install --atomic` in `cd.yml` (never run) | 🔄 | 🆕 Argo CD built on kind (6G: app-of-apps, auto-sync, self-heal) · **7.6 (Rollouts)** |
| D17 secrets | Secrets Manager + ESO | **Not wired.** No ExternalSecret in Helm, no Secrets Manager in Terraform | ✂️ | 🆕 kind: plain Secret from a filtered `.env`, built in 6E (`make kind-secret`, 6.5.6) · **7.3 (SOPS/ESO), 8.2 (ESO + Secrets Manager)** |
| D18 PII | Presidio | Regex `redact_pii` + `clean_user_text` | 🔁 | — |
| D10 cache | + singleflight coalescing | Not built | ✂️ | Optional |
| D20 routing | Model routing / escalation (< 10%) | Fallback chain only, no quality-based routing | ✂️ | App. A (1M tier) |
| **D25 (new)** | — | **Chat-history store portability** (DynamoDB is AWS-only) | ⏳ | **7.0.5** |
| **D26 (new)** | — | **North-south traffic: Gateway API (Envoy Gateway)**, not ingress-nginx (retired March 2026) | ✅ | 🆕 built and verified on kind (6E): Envoy Gateway 1.9.2, Gateway `public` (HTTP + HTTPS), same-origin HTTPRoute; DOKS and EKS reuse it · **6.4 / 6.5** |

- ⏳ 🆕 2.5 Record the Phase 6 session's decisions in the log:
  - Memory: keep the 8 GB Docker VM cap; stop the compose stack during kind work; lean add-ons;
    measure after each install.
  - North-south: same-origin routing. `/api/*` → api (the Gateway strips `/api`), `/*` → web.
    `NEXT_PUBLIC_API_URL=/api` in every environment, so no CORS and one web build.
  - Secrets on kind: a plain Secret built from a filtered `.env` by a make target (not SOPS /
    Sealed Secrets).
  - Auth on kind: both profiles, `clerk` for the browser smoke test and `devauth` for the k6 drills (6.6.1).

## Phase 3: Transformation plan ✅

- ✅ 3.1 `transformation-plan.md`: Batches A–F, Steps 1–18, risk register.
- ✅ 3.2 Risk front-loaded: go/no-go ranking gate at Step 5, before any infrastructure.
- ⏳ 3.3 *(low priority, local doc)* Update the header (still says "Phase 3 (plan for approval)")
  and add an "As built" section covering A1–A7 and the new Phase 6–9 structure.

---

## Phase 4: Execution, Steps 1–18 (+ 5b)

### Batch A: Foundation & product de-risking

#### Step 1: Repo scaffold & tooling ✅
- ✅ 1.1 Monorepo: `apps/{api,web,ingestion}`, `packages/{core,retrieval,recommender,evaluation,sources}`, `infra/`, `ops/`, `tests/`.
- ✅ 1.2 `pyproject.toml`: uv workspace, Python 3.12, **hatchling** editable install. Fixes `python -m core.aggregate` ModuleNotFoundError.
- ✅ 1.3 ruff (excludes `demo/`, `old/`, `Prompts/`) + mypy strict + pytest with an `integration` marker.
- ✅ 1.4 pre-commit: ruff + gitleaks.
- ✅ 1.5 Makefile (install / lint / fmt / type / test / check / eval-* / up / down / seed / helm-lint / urls …).
- ✅ 1.6 `.gitignore`, `.env.example`. `SERPAPI_API_KEY` and the Langfuse vars were added later (m-2, m-10).

#### Step 2: Data reframe, reviews → products ✅
- ✅ 2.1 Pydantic `Review`, `Product`, `Citation` (`packages/core/models.py`).
- ✅ 2.2 Aggregator: group by product → `avg_rating`, `review_count`, representative text.
- ✅ 2.3 `data-report.md` (product count, rating and volume distributions).
- ✅ 🔁 2.4 The plan assumed ~30 products. The data has **9**, and you chose to proceed with 9.
- ✅ 2.5 Unit tests: mean, count, dedup, edge cases.

#### Step 3: Qdrant + embeddings + hybrid retrieval ✅
- ✅ 3.1 Qdrant in `infra/compose/docker-compose.data.yml`.
- ✅ 3.2 Dense: OpenAI `text-embedding-3-small` @1536. Sparse: FastEmbed BM25 (`langchain-sparse`).
- ✅ 3.3 Hybrid query + `VectorStore` interface, so the backend can be swapped.
- ✅ 3.4 `qdrant-client` pinned `>=1.12,<1.13` to match server 1.12.4.
- ✅ 3.5 Integration test against real Qdrant with real embeddings.

#### Step 4: Ranking core ✅
- ✅ 4.1 `final = 0.7·relevance + 0.3·rating_norm·volume_confidence`, weights configurable.
- ✅ 4.2 Volume confidence, so 5★ from 2 reviews can't beat 4.5★ from 500.
- ✅ 4.3 Deterministic tie-breaking.
- ✅ 4.4 No-match floor. Re-done in M-1: an absolute dense cosine `min_semantic_similarity=0.30`
  instead of the relative RRF score.
- ✅ 4.5 Unit tests: a low-rated close match doesn't outrank a high-rated relevant one; weight sensitivity.

#### Step 5: Ranking eval + baseline (go/no-go gate) ✅
- ✅ 🔁 5.1 Golden set. The plan said ~50 queries; built **16 attribute-labelled queries** (9-product catalog).
- ✅ 🔁 5.2 Metrics: NDCG@3 / MRR / Recall@3 (the plan said @5; @3 fits a 9-item catalog).
- ✅ 5.3 Metric-correctness unit tests (perfect = 1.0, worst = 0).
- ✅ 5.4 Baseline **NDCG@3 0.80 · MRR 0.83 · Recall@3 0.82** → `eval-baseline.md` + `packages/evaluation/ranking/baseline.json`.
- ✅ 5.5 Go/no-go gate passed. `make eval-gate` blocks regressions (proven: 0.7972 vs floor 0.7522).

#### Step 5b: Cross-encoder reranker A/B ✅ (gated off)
- ✅ 5b.1 `BAAI/bge-reranker-base`, local.
- ✅ 5b.2 A/B against baseline: MRR improved, but NDCG@3 **−0.02** and Recall@3 **−0.07**.
- ✅ 5b.3 Gated off: `rerank_enabled=False` (`packages/core/config.py:33`). The data decided.

### Batch B: Inference pipeline & API

#### Step 6: LangChain chain + provider fallback ✅
- ✅ 6.1 LCEL chain plus versioned grounded-explanation prompt.
- ✅ 6.2 Structured output. The LLM writes **reasons only**; ranking fixes the product set.
- ✅ 6.3 Fallback: Groq `llama-3.3-70b-versatile` → OpenAI gpt-4o → Anthropic.
- ✅ 6.4 Live-verified: an invalid Groq key still answered via OpenAI.
- ⏳ 6.5 The **Anthropic leg** has never been called live (no key). It is unit-tested only. 🆕 `ANTHROPIC_API_KEY` is now set in `.env`, so one live call closes this (§10 D-13).

#### Step 7: Answer-quality eval ✅ 🔁
- ✅ 🔁 7.1 The RAGAS library was unusable (hard-imports `langchain_community.chat_models.vertexai`),
  so I built a custom LLM-judge harness with the same metric definitions.
- ✅ 🔁 7.2 Judge: OpenAI gpt-4o, not Claude (no Anthropic key).
- ✅ 7.3 Baseline: **answer-relevancy 0.94 · context-precision 0.65 · faithfulness 0.56** (`answer-quality-baseline.md`).
- ⏳ 7.4 Faithfulness 0.56 is the weak spot. See roadmap R5.

#### Step 8: FastAPI + DynamoDB history ✅
- ✅ 8.1 `/health`, `/metrics`, `/recommend`, `/chat` (SSE). Pydantic schemas.
- ✅ 8.2 DynamoDB-local in compose.
- ✅ 8.3 Single table: `PK=USER#{user_id}`, `SK=SESSION#{sid}#MSG#{nanos}#{rand}` (`packages/core/history.py`).
- ✅ 8.4 Isolation regression test for the demo's shared-session bug. IDOR verified live (bob sees 0 of alice's messages).
- ✅ 8.5 RTBF `DELETE /account`, DSAR `GET /account/export`, `DELETE /history`.
- ✅ 8.6 `ttl` attribute on every item, 90-day retention (M-11).
- ⏸️ ✂️ 8.7 The plan called for `docs/dynamo-access-patterns.md`. It was never written; the README carries
  the schema instead, and the README copy is **wrong** (§10 D-1).
- ⏳ 8.8 `DynamoChatHistory` is a concrete class with no interface. That makes it AWS-locked; see 7.0.5 / 7.10.1.

#### Step 9: 4-layer cache ✅
- ✅ 9.1 L0 in-process memo · L1 Redis embeddings · L2 Qdrant semantic cache · L3 Redis responses.
- ✅ 9.2 `catalog_version` invalidation, persisted on first read (fixed an `incr` collision bug).
- ✅ 9.3 `agg:` key is version-tagged too (m-7).
- ✅ 9.4 Measured hit rate 66.8%; a repeat query costs 0 SerpApi searches (2.94 s → 4.9 ms).
- ⏸️ ✂️ 9.5 Singleflight / stampede coalescing was planned but not built.

### Batch C: Cross-cutting production concerns

#### Step 10: Auth + rate limit + quotas ✅
- ✅ 10.1 Clerk RS256 via JWKS. Dev HS256 for local.
- ✅ 10.2 Fail-closed (C-2): dev bypass only when `APP_ENV=local` **and** `AUTH_DEV_BYPASS=true`. A non-local env with auth off refuses to boot.
- ✅ 10.3 Redis rate limit 30/min + 500/day per user → 429 + `Retry-After: 60` (verified 30 × 200 → 4 × 429).
- ✅ 10.4 Global SerpApi budget, 40/day and 250/month (C-4). TOCTOU race fixed (`e122888`).
- ⏳ 10.5 **Real-Clerk happy path** (HTTP 200 with a genuine browser-session token). The inspection
  only verified the 401s. **Do it in 7.5** (real domain, real TLS).

#### Step 11: Observability ✅ 🔁
- ✅ 🔁 11.1 OTel → **Jaeger** (planned: Tempo). Real `recommend.pipeline` spans.
- ✅ 11.2 Self-hosted Langfuse v2 + LangChain callback.
- ✅ 11.3 Prometheus scrapes `api:2011`. Real `http_requests_total` and `cache_*` counters.
- ✅ 11.4 Grafana datasource + `P2 Overview` dashboard as code (`ops/observability/grafana/`) (M-10).
- ✅ 11.5 Structured logging honours `LOG_LEVEL` (M-5). Telemetry failures log warnings (m-9).
- ⏳ 11.6 **Live-confirm token/cost in a Langfuse trace.** The README caption claims "per-request LLM
  cost". M-3 only confirmed the SDK *receives* usage. Spend one query, open the trace, screenshot the cost (7.5).

#### Step 12: Security + cost controls + kill switch ✅
- ✅ 12.1 Input sanitising at the edge (`clean_user_text`, calls `contains_injection_markers`).
- ✅ 12.2 Untrusted text in `<shopper_query>` / `<reviews>` delimiters plus an anti-injection clause.
- ✅ 12.3 Output guardrail `guard_output` with a hold-back buffer; the holdback is derived, not asserted (`070025a`).
  Re-ran the C-1 attack: leaked = False, obeyed = False.
- ✅ 🔁 12.4 PII: regex redaction, not Presidio. Runs before LLM, tracing and history (M-4).
- ✅ 🔁 12.5 Kill switch `LLM_ENABLED` (env var, not GrowthBook) → degraded mode, cache still served.
- ✅ 12.6 Cost cap via `max_output_tokens`.
- ✅ 12.7 Adversarial test fixtures.

#### Step 13: Failure-mode degradation ✅
- ✅ 13.1 Circuit breaker → popularity fallback when Qdrant is down (verified live: HTTP 200, `relevance_score=0.0`).
- ✅ 13.2 Redis: 0.25 s socket timeout plus a breaker (2 failures, 10 s cooldown). Outage went 24.7 s → 0.32 s (M-2).
- ✅ 13.3 LLM down → next provider, or the kill switch.
- ✅ 13.4 SerpApi down or over budget → `source_unavailable` (not `no_match`) + `source_unavailable_total{reason}`.
- ✅ 13.5 Chaos unit tests per dependency. Repeat on real clusters in 6.7 / 7.6.

### Batch D: Frontend

#### Step 14: Next.js frontend ✅ 🔄
- ✅ 14.1 Next.js 16 / React 19 / Tailwind v4 / Clerk.
- ✅ 14.2 Discover page consumes `/aggregate/stream` (`streamAggregate`): cards first, reasons after (M-8).
- ✅ 14.3 `AbortController` cancel, optimistic message, no-match and degraded banners.
- ✅ 14.4 Fabricated social proof removed. `DemoNotice` banner on every marketing page via `MarketingShell` (C-3, `bbf95de`).
- ✅ 14.5 Buy button relabelled "View on Google Shopping" (m-1).
- ⏳ 14.6 **Component tests + Playwright E2E were never built.** See roadmap R2.
- ⏳ 14.7 **Pricing page still makes false product claims** (§10 D-5).

### Batch E: Containers & orchestration

#### Step 15: Docker + compose parity ✅ 🔁
- ✅ 15.1 Multi-stage, non-root Dockerfiles for `api` and `web`.
- ✅ 15.2 Web image 1.29 GB → 439 MB via Next.js standalone output (m-4).
- ✅ 15.3 Three compose files (data / app / observability), **16 services**, ports 2001–2018.
- ✅ 15.4 Redis named volume + AOF (m-3). Qdrant API key enforced when set (m-6).
- ✅ 🔁 15.5 Distroless was not feasible: fastembed / onnxruntime are on the serving path. API image is ~725–774 MB.
- ⏸️ ✂️ 15.6 `worker` service (ARQ) was never built.

#### Step 16: Helm chart ✅ 🔄
- ✅ 16.1 `ops/helm/p2-recommender`: api / web Deployments + Services, api HPA, Qdrant StatefulSet + PVC,
  Redis, ServiceAccount (IRSA slot), optional Ingress.
- ✅ 16.2 `make helm-lint` (helm lint + kubeconform). 🆕 Now strict and once per environment (kind / doks / eks), against the Kubernetes 1.36.1 schemas.
- 🔄 ✂️ 16.3 Planned but not in the chart: KEDA ScaledObject, worker Deployment, PodDisruptionBudgets, Langfuse. PDBs get added in 6.4. 🆕 PDBs added in 6C; KEDA, the worker and Langfuse are still not built.
- 🔄 16.4 **Never installed on any cluster** (until Phase 6). 🆕 First installed on kind on 2026-10-07 (6E): release deployed, smoke 7/7. Real clusters: Phases 7–8.
- 🔄 16.5 The chart is **AWS-shaped**: `ingress.className: alb`, an IRSA annotation slot, a values comment
  claiming ESO, Redis as a Deployment with no PVC, image tag `latest`. Fixed by the portability refactor (6.4).
  🆕 6B fixed part of it: `alb` moved to the EKS overlay, the ESO comment, `latest` removed. 6C added the Redis PVC; routing → 6D.

### Batch F: Cloud IaC & CI/CD

#### Step 17: Terraform (AWS) ✅ 🔄
- ✅ 17.1 Root `main.tf`: VPC (3 AZs, `single_nat_gateway = true`, good for cost) + EKS (2–6 nodes, desired 2) + IRSA.
- ✅ 17.2 Local modules: `dynamodb` (PK/SK, PITR, TTL), `redis` (ElastiCache), `s3`, `ecr`.
- ✅ 17.3 `terraform validate` passes. A `tfplan` exists locally (gitignored; it can embed state).
- ⏳ ✂️ 17.4 Planned modules not built: `qdrant`, `cloudfront`, `waf`, `observability`. ESO / Secrets Manager wiring is missing too.
- ⏳ 17.5 S3 remote-state backend is **commented out** (`infra/terraform/versions.tf:12`).
- ⏳ 17.6 `tflint` and a cost estimate (infracost) were never run.
- ⏳ 17.7 **Never applied.** This is Phase 8.

#### Step 18: CI/CD + eval gate ✅ 🔄
- ✅ 18.1 `ci.yml` has 4 jobs on every push and PR: `quality` · `frontend` · `security` · `integration`.
- ✅ 🔁 18.2 The eval gate lives in the `quality` job (`evaluation.aggregator.gate`); there is no separate `eval-gate.yml`.
  It is a required check (`4537b0b`) and blocks if we stop beating Google Shopping's order.
- ✅ 18.3 Blocking `pip-audit` + `npm audit --audit-level=high` (`57fb93f`). 6 langchain advisories are listed by ID.
- ✅ 18.4 `cd.yml` skeleton: tag `v*` / dispatch → OIDC → ECR push → `helm upgrade --install --atomic`.
- ⏳ 18.5 `cd.yml` has **0 runs**. See Phase 8.4.
- ⏳ ✂️ 18.6 Planned CI items not built: Docker image build, **Trivy scan**, ECR push in CI, ArgoCD / Argo Rollouts.
  Argo CD gets built in 6.5 / 7.3, and Rollouts in 7.6.
- ⏳ 18.7 Missing from CI: `bandit`, `helm lint`, `terraform validate`, and a kind install test (6.8).
  🆕 The new chart contract tests (`tests/unit/test_helm_chart.py`) run under pytest, so CI exercises the chart if its runner has helm (not verified).

---

## Phase 4A: Aggregator pivot (ProductIQ) ✅

| # | Sub-step | Status | Evidence |
|---|---|---|---|
| A1 | SerpApi Google Shopping source + `Offer` model (price, store, rating, review_count, `buy_url`, thumbnail) | ✅ | 1 live call returned 40 offers. Offline fixture `tests/fixtures/serpapi_google_shopping.json` |
| A2 | Rank (same blend) + explain over offers. LLM writes reasons only | ✅ | Unit tests |
| A3 | `/aggregate` + 6 h result cache + global day/month budget guard | ✅ | `test_global_budget_guard_blocks_spend`. TOCTOU fix `e122888` |
| A4 | Frontend cards: price, store badge, thumbnail, "View on Google Shopping" | ✅ | m-1 relabel |
| A5 | `/aggregate/stream`: `offers` → `final` → `done`; Discover consumes it | ✅ | Cards land ~2.6 s before the answer |
| A6 | Aggregator eval on recorded fixtures + CI gate | ✅ | **NDCG@3 0.9413 / MRR 1.0000** vs Google **0.8240 / 0.8750**. `reports/aggregator-eval.md` |
| A7 | `source_unavailable` state + metric + alert rules | ✅ | `test_source_failure_is_reported_as_outage_not_no_match` |

- ⏳ A8 **Grow the eval set beyond 4 fixtures.** It is a sanity check, not a benchmark (the report says so).
  - ⏳ A8.1 Pick 6–10 more categories (appliances, laptops, shoes, books, …).
  - ⏳ A8.2 Record **1 SerpApi call per category** (≤ 10 of the 250/month) into `tests/fixtures/`.
  - ⏳ A8.3 Label relevance by hand, re-run `make eval-aggregator`, re-freeze the baseline, update the README numbers.

## Phase 4B: Inspection → remediation (27 findings) 🔄

*Source: `inspection-report.md` (2026-07-14) → `remediation-report.md` (2026-07-15).*

| ID | Finding | Status |
|---|---|---|
| C-1 | Prompt injection leaked the system prompt and persona | ✅ |
| C-2 | Fail-open auth | ✅ |
| C-3 | Fabricated marketing metrics | ✅ for homepage / about. **Pricing page still has false claims** (§10 D-5) |
| C-4 | SerpApi exhaustion looked like "no match"; one user could drain the quota | ✅ |
| M-1 | No-match never fired | ✅ |
| M-2 | 24.7 s Redis hang | ✅ |
| M-3 | Langfuse cost = 0 | 🔄 SDK fix landed; **live trace never re-confirmed** (11.6 → 7.5) |
| M-4 | Raw PII in Langfuse | ✅ |
| M-5 | No logging | ✅ |
| M-6 | 5 tests silently skipped | ✅ (now 121 collected; 112 offline pass). 🆕 5 DynamoDB-local tests still skip quietly when it's down (§10 D-12) |
| M-7 | Evals scored the wrong path | ✅ |
| M-8 / M-9 | SSE was dead code; cold latency | ✅ / 🔄 (cold is bound by SerpApi) |
| M-10 | Grafana empty; alerts not loaded | ✅ (10 rules, 4 groups) |
| M-11 | DynamoDB TTL inert | ✅ code · ⏳ live check (7.5 / 8.2) |
| **M-12** | **Image CVEs (1 CRITICAL / 10 HIGH)** | **🔄 Partial: the one finding still open** |
| m-1…m-11 | Minor findings | ✅ all |

- 🔄 **Close M-12:**
  - ⏳ M-12.1 Re-scan the current image (`docker scout cves p2-recommender-api` or Trivy) and record counts. The last numbers are from July.
  - ⏳ M-12.2 Relax `requires-python` to allow 3.13; check onnxruntime / fastembed / qdrant-client wheels exist.
  - ⏳ M-12.3 Rebase to `python:3.13-slim`, rebuild, run the full test suite + `make eval-gate`.
  - ⏳ M-12.4 Re-scan. Document whatever CRITICAL / HIGH remains, by CVE ID and reason.
  - ⏳ M-12.5 *(Larger)* Split sparse embedding into its own service so the API image drops onnxruntime (also R9).

## Phase 4C: Honesty & cleanup pass ✅ (2026-07-28 → 08-08)

- ✅ `23ebdf2` Working docs and local tooling kept out of the published tree.
- ✅ `14a1c21` Untracked build artifacts, closed the `tfplan` gitignore gap, added LICENSE.
- ✅ `4537b0b` Ranking eval gate is a required check on every PR.
- ✅ `38fba07` README reframed as one ranking core with two retrieval backends.
- ✅ `bbf95de` Fabricated customer proof removed; demo banner made unmissable.
- ✅ `e122888` TOCTOU race in the global SerpApi budget guard closed.
- ✅ `64df1b9` Eval reports published; a misleading constant renamed.
- ✅ `070025a` Streaming guardrail holdback derived, not asserted.
- ✅ `57fb93f` Blocking CVE scan (pip-audit + npm audit), PR #1.
- ✅ `e876eb3` Removed every claim the repository can't verify.
- ✅ `f146401` Screenshots re-captured **after** the UI cleanup (2026-08-01).

---

## Phase 5: Hardening 🔄

*`hardening.md` was written on 2026-05-31 and is out of date. The "true today" column is what the repo shows now.*

| Item | `hardening.md` says | True today | To do / where it closes |
|---|---|---|---|
| Secrets audit | Done; Secrets Manager + ESO | gitleaks in pre-commit ✅. **ESO / Secrets Manager not wired** ✂️ | Fix the doc. SOPS/ESO in 7.3, ESO + Secrets Manager in 8.2 |
| Dependency audit | Done | ✅ pip-audit + npm audit, blocking in CI | Remove the 6 ignore IDs after R3 |
| License audit | Done | ✅ (one-off, May) | Re-run `pip-licenses` after R3 / M-12 |
| Code scan (bandit) | Done; "run in CI" | 0 issues locally ✅. **Not in `ci.yml`** | ⏳ 5.2 |
| Container scan | Partial; "Trivy job added" | **No Trivy job in `ci.yml`** | ⏳ 5.3 (and before every push in 7.2) |
| Eval gate | Done | ✅ aggregator gate in CI; catalog gate local | — |
| Prompt injection | Done | ✅ (C-1 fix) | — |
| PII | Done | ✅ (M-4 fix) | — |
| RTBF / DSAR | Done | ✅ | — |
| Rate limit / kill switch / budget | Done | ✅ (+ global SerpApi budget) | — |
| Chaos / degradation | Done | ✅ unit + live in compose (Qdrant, Redis) | Repeat on clusters: 6.7, 7.6 |
| Runbook | Done | ✅ `runbook.md`, `monitoring-runbook.md` | Add kind / DOKS / EKS playbooks (6.9, 7.8, 8.5) |
| Alert rules | Partial | ✅ 10 rules loaded in Prometheus | Alertmanager + real receiver: 6.5 (local), **7.3** (real) |
| Cost alerts | Partial | ⏳ | DO billing alert (7.0.2), AWS Budget (8.0.2) |
| Log retention | Documented | ✅ documented | Loki retention in 7.3 (optional) |
| Load test | Partial | ✅ k6 script fixed (m-8); cached p95 7.59 ms @ 50 VUs on a laptop | **7.6** (real cluster), 8.3 |
| Backup / restore drill | Deferred | ⏳ never drilled | **7.6** (Velero + Qdrant snapshot), 8.3 (DynamoDB PITR) |
| Image slimming | Deferred | 🔄 web done (439 MB); api not | M-12 / R9 |
| On-call | Deferred | ⏳ | ⏸️ Out of scope for a portfolio; say so |

- ⏳ 5.1 Rewrite `hardening.md` to match the "true today" column.
- ⏳ 5.2 Add `bandit -r packages apps` to the CI `security` job.
- ⏳ 5.3 Add an `image-scan` CI job: `docker build` api + web → `aquasecurity/trivy-action`
  (fail on CRITICAL; HIGH as report-only until M-12 closes).
- ⏳ 5.4 Add `helm lint` + `terraform validate` (`-backend=false`) to CI. Cheap, no cloud needed. 🆕 Locally, `make helm-lint` now lints each environment (strict).

---

## Phase 6: Deployment using kind 🔄 ($0, local)

> **What kind is:** *Kubernetes IN Docker*. Each "node" is a Docker container on **your one machine**.
> It runs the real Kubernetes API, scheduler and kubelet, so manifests, Helm charts, RBAC,
> NetworkPolicies, HPAs and operators behave as they would on a real cluster.
> **What kind is not:** a production cluster, for any number of users. It has no real load
> balancer, no cloud disks, no node autoscaling, no HA (one machine), no SLA, and its performance
> numbers measure only your laptop.
> **Its job:** prove the chart and platform add-ons install and behave correctly *before* you
> pay per hour to debug them on DOKS or EKS. Nothing "scales up" from kind: you throw it away and
> install the **same chart with a different values file** on the real cluster.

### 🆕 How the Phase 6 session groups the work

| Sub-step | Todo IDs | Status |
|---|---|---|
| **6A** Cluster + environment risks | 6.2, 6.3, 6.5.8 | ✅ verified · not yet committed |
| **6B** Chart structure | 6.4.1, 6.4.3, 6.4.8, 6.4.9, 6.4.12 + F2, F3 | ✅ verified · not yet committed |
| **6C** Chart hardening | 6.4.4–6.4.7 + F5, F8, F9, F13, F14 | ✅ verified · not yet committed |
| **6D** Per-environment wiring | 6.4.2, 6.4.10, 6.4.11 + F4, F6, F7, F15 | ✅ verified · not yet committed |
| **6E** Add-ons + first deploy | 6.2.3, 6.3.3, 6.5.1–6.5.3, 6.5.6, 6.6.1–6.6.4 + F17–F20 | 🔄 verified on kind · browser sign-in pending · not yet committed |
| **6F** Monitoring | 6.5.4, 6.6.5 + F21–F24 | ✅ verified · not yet committed |
| **6G** GitOps | 6.5.5 + F18, F25–F28 | ✅ verified · not yet committed |
| **6H** Drills | 6.7.1–6.7.8 + F29–F32 | ✅ 8/8 verified · not yet committed |
| **6I** CI, evidence, teardown | 6.8, 6.9 + F33 | ✅ verified locally · CI's GitHub run after your push · not yet committed |

### 🆕 Findings: F1–F16 from the chart recon (before any install), F17–F20 from the first install (6E)

| # | Finding | Status / where it's fixed |
|---|---|---|
| F1 | The Docker VM is capped at 8 GB (`~/.wslconfig`); compose and kind don't fit together | ✅ decided: stop compose during kind work, lean add-ons |
| F2 | `replicas` set while the HPA is on, so every upgrade fights the HPA | ✅ 6B |
| F3 | Selectors were `app: api`, which can't change after install | ✅ 6B |
| F4 | The Ingress forwards `/api/...` to FastAPI unstripped, so every API call 404s | ✅ 6D: HTTPRoute strips `/api`; the Ingress is gone |
| F5 | The web pod has no env (`CLERK_SECRET_KEY`) and no probes | ✅ 6C |
| F6 | The api pod has no `DYNAMODB_ENDPOINT`, so it falls back to `localhost:2003` inside the pod | ✅ 6D |
| F7 | `history.py:50-51` fake `local` credentials would override IRSA / Pod Identity on EKS | ✅ 6D |
| F8 | The chart's Redis has no PVC / AOF, so a restart re-spends SerpApi quota | ✅ 6C |
| F9 | `QDRANT_API_KEY` is set but the chart's Qdrant doesn't enforce it; no probes | ✅ 6C |
| F10 | The web→API URL is baked into the JS bundle at build time | ✅ decided: same-origin `/api` (built in 6D) |
| F11 | Helm 4: `--atomic` deprecated, `--wait` defaults to `hookOnly`; `cd.yml` doesn't pin Helm | ⏳ §10 D-14 |
| F12 | Windows can't reach LoadBalancer IPs on Docker Desktop | ✅ 6A: NodePort + `extraPortMappings` |
| F13 | The api and web images set `USER` by name, so `runAsNonRoot` would fail at container creation (the kubelet can't verify a named user) | ✅ 6C: numeric `runAsUser: 10001` |
| F14 | Qdrant runs as root, and under a read-only root it panics without a writable snapshots dir | ✅ 6C: `v1.12.4-unprivileged` + emptyDirs |
| F15 | dynamodb-local extracts its SQLite native library into `/tmp` and loads it, so `/tmp` must allow exec (its `USER` is also a name, like F13) | ✅ 6D: disk-backed emptyDir + numeric `runAsUser` |
| F16 | The api creates the DynamoDB table once per process (`ensure_table` behind `lru_cache`), so an emulator restart breaks history until the api restarts | ⏸️ kind-only, documented: real DynamoDB never loses tables |
| F17 | Kubernetes service links: the Service named `web` injects `WEB_PORT=tcp://<ip>:2012` into every pod, overriding the image's `WEB_PORT=2012`, so Next.js started on port 3000. The first install never became ready and `--rollback-on-failure` uninstalled it (PVCs and the Secret survived, as they should) | ✅ 6E: `enableServiceLinks: false` on every pod + `WEB_PORT` from `web.port` (chart 0.5.0) |
| F18 | Each api pod downloads the Qdrant/bm25 sparse model from the Hugging Face Hub (unauthenticated) and tiktoken's files on its **first request**, after it already reports Ready: 23 s for the first `/recommend` (warm: 3–8 ms). It happens even on a cache hit (dependencies are built before the cache check), on every rollout and scale-up, and makes huggingface.co a runtime dependency | ✅ 6G: both caches baked into the image, `HF_HUB_OFFLINE=1`: first request on a fresh pod 0.46 s, no downloads (the old image fails offline) |
| F19 | GNU make on Windows, run from PowerShell, finds no `sh.exe` and runs recipes in cmd.exe, so sh syntax (`if …; then`, `$$(…)`) fails | ✅ 6E: the kind targets are shell-neutral (logic in make functions or Python); older targets → §10 D-15 |
| F20 | In-cluster traffic is plain HTTP, so the Qdrant API key crosses the pod network unencrypted (the client warns) | ⏸️ acceptable on kind; decide TLS or a mesh for DOKS/EKS (Phases 7–8) |
| F21 | `ApiDown` was `up{job="p2-api"} == 0`. On Kubernetes an api scaled to zero has no scrape targets, so no `up` series exists and the alert could never fire | ✅ 6F: `absent(up{job="p2-api"} == 1)`; promtool tests (the old rule fails them); fired live on kind |
| F22 | Pod templates carried `helm.sh/chart` and the app version, so every chart bump restarted every pod, including the single-replica Qdrant and Redis | ✅ 6F: pod templates use selector labels + `part-of` only |
| F23 | kube-prometheus-stack 92.0.0 ships Grafana 13.2.3, which pinned 14 CPU cores on kind (SQLite lease errors in its secure-values cleanup) and never became Ready | ✅ 6F: Grafana pinned to 12.4.12 + a 1-CPU limit; re-test 13.x before unpinning |
| F24 | The chart tests decoded `helm template` output with the Windows locale (cp1252), mangling `—` in the alert summaries | ✅ 6F: decode as UTF-8 |
| F25 | Argo CD runs Helm post-install hooks on **every** sync, and the seed Job recreated the collection each time, so GitOps would have blanked the catalog on every sync | ✅ 6G: points carry a catalog fingerprint; `--skip-if-current` re-indexes only when the catalog changed (seen: "skipped" on a sync) |
| F26 | `<sha>-dirty` named every uncommitted state of a commit, so a rebuild reused the tag and Kubernetes saw nothing to roll out | ✅ 6G: `infra/kind/image_tag.py` adds a hash of the image inputs |
| F27 | Argo CD's default client-side diff kept qdrant, redis and the HTTPRoute OutOfSync after every sync (fields the API server defaults) | ✅ 6G: server-side diff, matching server-side apply |
| F28 | A `git push` through `kubectl port-forward` stalls once the pack flows (Windows; WebSocket and SPDY alike), though the same push inside the pod works | ✅ 6G: the commits travel as a git bundle over `kubectl exec` stdin |
| F29 | Argo CD syncs had no timeout, and a broken release never turns healthy, so its sync waited forever before the PostSync seed hook; auto-sync won't start another sync meanwhile, so the rollback commit sat unapplied | ✅ 6H: `controller.sync.timeout.seconds: 180`; the rollback then applied by itself |
| F30 | Losing a node failed **43%** of requests for the whole 6-min outage: the single Envoy Gateway controller died with the node, so the surviving proxy never dropped the dead pods | ✅ 6H: controller ×2 (hard spread), proxies ×2 + PDB, and a BackendTrafficPolicy (2 s connect timeout, retry only connection failures, passive ejection): **0.27%**, only while the node was being declared dead |
| F31 | After a node loss the evicted pods all land on the surviving node and stay there (Kubernetes never rebalances; the spread is soft) | ⏸️ restart or a descheduler; decide in Phase 7 |
| F32 | During a Redis outage, per-user rate limits aren't enforced (`incr_window` returns 0: fail-open by design, availability first) | ⏸️ documented; check whether the global SerpApi budget guard also fails open (not tested) |
| F33 | chart-testing's yamllint wants two spaces before inline comments; `values.yaml` had one (23 errors), so the CI job would have failed on its first run | ✅ 6I: fixed in all values files; every render byte-identical |

### 6.1 Local Docker baseline ✅
- ✅ 6.1.1 `make upv` → 16 services up → seed → `make urls`.
- ✅ 6.1.2 `/health` 200, `/aggregate` live offers, `/chat` SSE, Jaeger / Prometheus / Grafana / Langfuse reachable.
- 🆕 The compose stack is stopped while Phase 6 runs (`make down` keeps the volumes; `make full` brings it back).

### 6.2 Tooling 🔄
- 🔄 6.2.1 Install `kind`, `kubectl`, `helm`, `k9s` (optional), `kubectx`/`kubens` (optional).
  - ✅ 🆕 kind v0.32.0 · kubectl v1.36.1 · helm **v4.1.4** · kubeconform v0.7.0.
  - 🆕 Helm 4 changes: `--atomic` is deprecated (use `--rollback-on-failure`); `--wait` now defaults to `hookOnly`.
  - ⏳ k9s (optional) · ⏳ kubectx/kubens (optional).
  - 🆕 sops / age / kubeseal aren't needed (secrets decision in 6.5.6).
- ✅ 🔁 6.2.2 Docker memory. The plan said give it ≥ 10–12 GB. 🆕 Decided instead: keep the 8 GB cap,
  stop compose during kind work, keep add-ons lean, measure after each install.
  - ✅ 🆕 Measured idle: kind ≈ 1.25 GB (control plane 840 MiB, workers ~200 MiB each); ~5.9 GB of the VM available.
  - ✅ 🆕 Measured: every kind node reports the whole VM as allocatable (8133208Ki, 16 CPUs), so the
    scheduler sees 3× the real memory. The api HPA is capped at 4 replicas on kind.
  - ✅ 🆕 Measured after each 6E install (the 3 node containers): empty 1,328 MiB → metrics-server
    1,377 → Envoy Gateway 1,713 → cert-manager 2,121 → Gateway + proxy 2,224 → app 4,253. The add-ons
    cost ~0.9 GB, mostly kube-apiserver holding 24 new CRDs (610 MiB). The app's pods use ~680 MiB
    (api ~210 MiB each); the rest is node-level. ~3.6 GB of the VM is left for 6F.
  - ✅ 🆕 6F: kube-prometheus-stack added ~1.3 GB (4,027 → 5,322 MiB); Prometheus ~360 MiB, Grafana ~270 MiB.
    ~2.5 GB left for Argo CD (6G).
  - ✅ 🆕 6G: Argo CD added ~0.5 GB (kind 5.83 GB in all); controller ~260 MiB. ~2 GB of the VM left.
- ✅ 🔁 6.2.3 `helm repo add` for each add-on in 6.5. Pin chart versions in a file (no floating `latest`). (6E)
  🆕 Pinned in `infra/kind/addons/versions.env` (metrics-server 3.14.0, Envoy Gateway 1.9.2, cert-manager
  v1.21.2: latest stable on 2026-10-06), included by the Makefile. 🔁 Installs pass `--repo <url>` (or an
  OCI ref) instead of `helm repo add`, so a fresh machine or CI needs no local repo state.

### 6.3 Cluster ✅
- ✅ 6.3.1 `infra/kind/kind-config.yaml`: 1 control-plane + 2 workers. 🆕 NodePorts 30080/30443 published
  on 127.0.0.1:80/443 (not 0.0.0.0); `kindest/node` v1.36.1 pinned by digest.
- ✅ 6.3.2 `kind create cluster --name p2 --config infra/kind/kind-config.yaml` (🆕 `make kind-up` / `make kind-down`).
- ✅ 6.3.3 Images: `docker build` api + web with a **git-SHA tag** → `kind load docker-image`.
  🆕 The web image is built with `NEXT_PUBLIC_API_URL=/api`. (6E)
  🆕 `make kind-images`: tag = short SHA, plus `-dirty` when the image inputs have uncommitted changes
  (today `56b28de-dirty`); 67 s with a warm cache; loaded on all 3 nodes. Bundle check: no `localhost:2011`,
  no Clerk example key; the real publishable key and the `/api` calls are baked in.
- ✅ 6.3.4 `kubectl get nodes -o wide`: 3 Ready nodes (v1.36.1, containerd 2.3.1).
- ✅ 🆕 6.3.5 Windows → NodePort path proven (`infra/kind/nodeport-probe.yaml`): HTTP 200 on `127.0.0.1`
  and `app.localhost` with curl.exe.
  - .NET (`Invoke-WebRequest`) can't resolve `*.localhost`. From PowerShell, use curl.exe or `127.0.0.1` + a `Host:` header.
  - One early request failed and a clean re-run didn't reproduce it, so smoke tests wait for ready
    EndpointSlices and retry.

### 6.4 Chart portability refactor ✅ (done once; Phases 7 and 8 reuse it)
- ✅ 6.4.1 Layered values: `values.yaml` (common) + `values-kind.yaml` + `values-doks.yaml` + `values-eks.yaml`.
  🆕 The overlays hold only what's decided now. (6B)
- ✅ 🔁 6.4.2 Replace the ALB-only Ingress with **Gateway API `HTTPRoute`s** (toggle `gateway.enabled`).
  Keep the ALB Ingress as an EKS-only option. **Don't adopt ingress-nginx**: it was retired in
  March 2026 and gets no more security fixes. (6D)
  - 🆕 Decided: same-origin routing. `/api/*` → api with the `/api` prefix stripped, `/*` → web.
  - 🆕 This also fixes F4: today's Ingress forwards `/api/...` unstripped, so every API call would 404.
  - ✅ 🆕 Built in 6D: one HTTPRoute (`/api/*` → api with the prefix stripped and a 120 s timeout for
    streamed answers; `/*` → web), attached to Gateway `public` in namespace `gateway`.
  - 🔁 🆕 The ALB Ingress was **dropped**, not kept as an EKS option: an ALB can't be relied on to strip
    `/api`. EKS uses the same HTTPRoute through Envoy Gateway behind an NLB (8.2.5).
- ✅ 6.4.3 Fix the values comment that claims ESO. The chart only expects a Secret named `p2-secrets`;
  *how* it's created is per environment (6.5.6, 7.3.6, 8.2.4). (6B)
- ✅ 6.4.4 Probes: readiness / liveness / startup on api (`/health`) and web. Startup probe sized for the slow ML import. (6C)
  🆕 The hardened api took 28 s to report healthy, so its startup probe allows 5 s × 36. Qdrant uses `/readyz` / `/livez` (they answer without the API key), Redis `redis-cli ping`, web `/` + a TCP check.
- ✅ 6.4.5 `securityContext`: `runAsNonRoot`, drop ALL capabilities, `readOnlyRootFilesystem` where possible
  (with a tmp `emptyDir`), `seccompProfile: RuntimeDefault`. (6C)
  🆕 Read-only root on all four workloads, with emptyDirs / PVCs exactly where each image writes (found by running each image hardened in Docker). Pod Security Admission `restricted`: 0 warnings.
- ✅ 6.4.6 **PodDisruptionBudgets** for api / web (closes ✂️ 16.3) + `topologySpreadConstraints` across nodes. (6C)
  🆕 `maxUnavailable: 1` (never blocks a drain outright); soft spread with `matchLabelKeys: [pod-template-hash]`.
- ✅ 6.4.7 Redis: StatefulSet + PVC, or document it as a disposable cache. The chart today loses the cache on
  restart, which re-spends SerpApi quota (the compose fix m-3 never reached the chart). (6C)
  🆕 StatefulSet with AOF on a PVC; in the Docker check a key survived a container restart.
- ✅ 6.4.8 `storageClassName` per environment: kind `standard` · DOKS `do-block-storage` · EKS `gp3`.
  🆕 Pulled forward into 6B, because `volumeClaimTemplates` can't change after the first install.
- ✅ 6.4.9 Image registry + `imagePullSecrets` values. Tags = git SHA, never `latest`. 🆕 Empty, `latest` and
  numeric tags fail the render (plain `--set` parses an all-digit SHA such as 1234567 as a number). (6B)
- ✅ 6.4.10 Seeding as a Helm **post-install hook Job** (the k8s version of `make seed`). (6D)
  🆕 It runs once after install, not on upgrades: the indexer recreates the collection, so an upgrade-time
  re-seed would briefly empty the catalog mid-rollout. Opt in with `seed.onUpgrade=true`.
- ✅ 6.4.11 DynamoDB per environment: kind → `dynamodb-local` Deployment (**practice only**); DOKS → see 7.0.5; EKS → real table via IRSA / Pod Identity. (6D)
  - ✅ 🆕 F6: the template derives `DYNAMODB_ENDPOINT`: `http://dynamodb:8000` on kind, empty (real AWS)
    elsewhere. It's always set, so the Secret's compose value can't leak into a cluster.
  - ✅ 🆕 F7: `history.py` passes dummy credentials only to the emulator; real AWS uses boto3's default
    chain. 3 new unit tests; the 5 history-store tests pass against DynamoDB-local.
- ✅ 6.4.12 `make helm-lint` green for **each** values file. 🆕 `helm lint --strict` + `kubeconform -strict`
  (Kubernetes 1.36.1): 10/10 valid for kind, doks and eks. (6B)
- 🆕 Added from the recon:
  - ✅ 6.4.13 F3: standard selectors `app.kubernetes.io/{name,instance,component}` before the first install. (6B)
  - ✅ 6.4.14 F2: no `replicas` on the api Deployment while the HPA is on. (6B)
  - ✅ 6.4.15 F5: the web pod gets only `CLERK_SECRET_KEY` (a `secretKeyRef`, not the whole Secret) + probes. (6C)
  - ✅ 6.4.16 F9: Qdrant enforces `QDRANT_API_KEY` and gets probes + a headless governing Service. (6C) `/collections` returns 401 without the key and 200 with it.
  - ✅ 6.4.17 Chart contract tests: `tests/unit/test_helm_chart.py`, 13 passing (skipped without helm). (6B) 🆕 29 after 6C, 41 after 6D, 45 after 6E.
  - ✅ 6.4.18 Server-side dry run on kind's API server: 10/10 objects accepted. (6B) 🆕 14/14 after 6C; 23/23 after 6D (the HTTPRoute waits for its CRD, 6E). 6E: the real install applied all
    24 objects with 0 warnings.
  - ✅ 🆕 6.4.19 Every image run hardened in Docker before any install (read-only root, numeric non-root user,
    capabilities dropped): api ✅ (healthy in 28 s; fastembed caches in `/tmp`), web ✅, Redis ✅ (AOF survives a
    restart), Qdrant ✅ once its snapshots dir was writable (F14). (6C)
  - ✅ 🆕 6.4.20 F13: numeric `runAsUser` for api and web, because their images set `USER` by name. (6C)
  - ✅ 🆕 6.4.21 Pod Security Admission `restricted`, server-side dry run: 0 warnings for the 6C chart; the 6B
    chart triggers 4 (negative control). (6C) 6D: still 0 warnings across 23 objects, including
    dynamodb-local and the seed Job.
  - ✅ 🆕 6.4.22 NetworkPolicies: default-deny ingress + one allow per real path (Gateway → web/api,
    monitoring → api, api + seed → qdrant, api → redis, api → dynamodb). (6D)
  - ✅ 🆕 6.4.23 dynamodb-local run hardened in Docker: table created, item written and read back. (6D)
  - ✅ 🆕 6.4.24 HTTPRoute validated against the Gateway API schema (kubeconform + CRD catalog); the
    server-side check follows once Envoy Gateway installs the CRDs (6E). (6D) 6E: Envoy Gateway accepted it
    (Accepted + ResolvedRefs = True, attached to both listeners).
  - ✅ 🆕 6.4.25 F17: `enableServiceLinks: false` on all six pod templates and `WEB_PORT` set from `web.port`;
    4 new contract tests; chart 0.5.0. A render of the 6D chart has none of these lines (negative control). (6E)

### 6.5 Platform add-ons on kind 🔄 (the same set goes on DOKS in 7.3)
- ✅ 6.5.1 **metrics-server** (kind needs `--kubelet-insecure-tls`). Needed for the HPA.
  🆕 Chart 3.14.0 (app 0.9.0), installed in 34 s; `kubectl top` works; the api HPA reads `cpu: 1%/70%`. (6E)
- ✅ 6.5.2 **Envoy Gateway** (Gateway API): `GatewayClass` → `Gateway` → `HTTPRoute`s for `app.localhost` / `api.localhost`.
  🆕 With the same-origin decision this becomes one host, `app.localhost`, with `/api/*` → api.
  Exposed as NodePort 30080/30443.
  🆕 The chart's HTTPRoute attaches to Gateway `public` in namespace `gateway` (6E creates it). Envoy's
  proxy pods run in `envoy-gateway-system`, which the NetworkPolicies allow.
  - ✅ 🆕 Envoy Gateway 1.9.2 (Gateway API v1.6.1 CRDs, experimental channel), installed in 39 s. An
    `EnvoyProxy` makes the proxy Service a NodePort on 30080/30443 with `externalTrafficPolicy: Cluster`:
    the proxy pod runs on a worker, but the published ports land on the control plane. (6E)
  - ✅ 🆕 GatewayClass `eg` → Gateway `gateway/public` (HTTP :80 + HTTPS :443) → the chart's HTTPRoute.
    Only namespaces labelled `gateway-access=public` can attach routes. Files: `infra/kind/platform/`. (6E)
  - ✅ 🆕 From Windows, `http://app.localhost` reaches Envoy (404 before the app, 200 after).
- ✅ 6.5.3 **cert-manager** with a self-signed `ClusterIssuer` (Let's Encrypt comes in 7.3).
  🆕 v1.21.2, installed in 68 s. Self-signed root → local CA `p2-local-ca` → certificate for `app.localhost`
  (ECDSA P-256, 90 days, renews at day 60) on the Gateway's HTTPS listener. From Windows it verifies
  against the CA (exit 0) and is refused without it (exit 60). Export the CA's public cert from Secret
  `cert-manager/p2-local-ca` (`ca.crt`); Windows curl (Schannel) also needs `--ssl-revoke-best-effort`,
  because a private CA publishes no revocation list. (6E)
- ✅ 6.5.4 **kube-prometheus-stack** (Prometheus Operator + Grafana + Alertmanager):
  🆕 Chart 92.0.0 (pinned in `versions.env`), lean values in `infra/kind/addons/kube-prometheus-stack.yaml`.
  kind's 127.0.0.1-bound control-plane components aren't scraped, so there are no false "down" alerts:
  only Watchdog/InfoInhibitor fire (routed to a null receiver). Installed by `make kind-addons`. (6F)
  - ✅ `ServiceMonitor` for api `/metrics`. 🆕 In the app chart (`monitoring.enabled`, on for kind); the job
    label is relabelled to `p2-api` as in compose. Both api pods scraped `up`, through the NetworkPolicy.
  - ✅ Convert `ops/observability/alerts.yaml` → a `PrometheusRule` CRD (same 10 rules).
    🔁 🆕 The rules file **moved into the chart** (`files/alerts.yaml`), and compose mounts it from there:
    one file for both. All 10 loaded in Prometheus. `make alerts-test` runs `promtool check rules` and 4
    rule unit tests (Docker, no install).
  - ✅ Load the `P2 Overview` dashboard through the Grafana sidecar ConfigMap. 🆕 The JSON moved to
    `files/dashboards/` (compose mounts it too); it shows live api traffic on kind.
  - ✅ 🔁 Alertmanager → a test receiver. 🆕 Not webhook.site: a local `alert-sink` in `monitoring` logs
    each alert, so payloads never leave the machine (`infra/kind/platform/40-alert-sink.yaml`).
- ✅ 🔁 6.5.5 **Argo CD** (GitOps, closes ✂️ D16): an app-of-apps pointing at the repo; the app syncs from `ops/helm`. Practice is free here.
  🆕 Built in 6G: Argo CD v3.5.3 (chart 10.9.6, lean: no Dex, notifications or ApplicationSets).
  - 🔁 "Pointing at the repo": the Phase 6 work isn't pushed yet, so Argo CD syncs from an **in-cluster
    git server** holding a copy of the chart and the apps from the working tree (`make kind-gitops`).
    After you push, change `repoURL` in `ops/argocd/kind/root.yaml` and `apps/p2.yaml`; nothing else.
  - ✅ App-of-apps: `root` → `ops/argocd/kind/apps/` → `p2` (chart + `values-kind.yaml` + `release.yaml`, which
    carries the image tag: written by `make kind-gitops`, by CI on a real cluster). Auto-sync + self-heal.
  - ✅ Handover from Helm with no downtime: only Helm's release record is deleted; Argo CD adopted the
    running objects. Synced 26 · OutOfSync 0 · Healthy 35 (screenshot taken).
  - ✅ Self-heal: a deleted NetworkPolicy came back in 0.6–1.2 s (115.6 s on the first try, right after
    the controller restarted). A sync runs the seed as a PostSync hook, which skipped (F25).
  - `make kind-argocd` (install + git server + push + handover) re-runs as a no-op in 15 s. Deploy from
    then on: `make kind-images kind-gitops`, not `kind-deploy` (Helm and Argo CD would fight).
- ✅ 🔁 6.5.6 **Secrets.** The plan said SOPS + age or Sealed Secrets. 🆕 Decided: a make target builds a plain
  Secret from a filtered `.env` (nothing secret in git). GitOps-managed secrets move to DOKS (7.3.6).
  Never commit plaintext `.env`.
  - ✅ 🆕 Built: `make kind-secret PROFILE=…` runs `infra/kind/kind_secret.py`. An allow-list copies 20 keys
    and leaves out 56 (compose URLs and ports, Langfuse, build-time `NEXT_PUBLIC_*`). Values are never
    printed. Server-side apply, so no `last-applied-configuration` annotation holds plaintext; base64
    `data`, so a profile switch removes the keys it drops. Refuses non-kind contexts. 15 unit tests. (6E)
  - ✅ 🆕 The type gate (`make type` and CI) now covers `ops/` and `infra/`. (6E)
- ⏳ 6.5.7 *(Optional)* OTel Collector + Jaeger operator, Loki + Grafana Alloy for logs.
- ✅ 6.5.8 **NetworkPolicy enforcement test.** 🆕 kind's default CNI (kindnet) enforces ingress policy: `ok`
  before a default-deny, 3/3 timeouts after (`infra/kind/netpol-probe*.yaml`). No Calico or Cilium needed.
  Egress not tested yet.

### 6.6 Deploy the app 🔄
- ✅ 6.6.1 Create Secrets (6.5.6). Use `AUTH_DEV_BYPASS=false` and real Clerk dev keys.
  - ✅ 🆕 Decided: **both profiles.** A make target builds the Secret as `PROFILE=clerk` (APP_ENV=dev,
    real Clerk RS256; used for the 6E browser smoke test) or `PROFILE=devauth` (APP_ENV=local, no
    `CLERK_JWKS_URL`; HS256 tokens from `mint_tokens.py` for the 6H k6 drills, because Clerk session
    tokens last ~60 s). `AUTH_DEV_BYPASS` stays false in both. Switching = recreate the Secret + restart the api.
  - ✅ 🆕 Both verified. devauth: 22 keys including `AUTH_DEV_SECRET`. Switching to clerk took 22 s (rolling
    restart) and added `CLERK_JWKS_URL` and removed `AUTH_DEV_SECRET`. The cluster is left on **clerk**.
- ✅ 6.6.2 Deploy through Argo CD (or `helm install p2 ops/helm/p2-recommender -f values-kind.yaml -n p2 --create-namespace`).
  🆕 Helm 4 flags: `--rollback-on-failure --wait=watcher`; pass the tag with `--set-string`.
  - ✅ 🆕 `make kind-deploy` (Helm; Argo CD comes in 6G). The first attempt failed on F17, and
    `--rollback-on-failure` uninstalled it after the 10-minute wait; PVCs and the Secret survived. After the
    fix: deployed in 129 s, 0 API-server or Pod Security warnings, 7/7 pods Ready, api and web spread
    across both workers.
- ✅ 6.6.3 Seed Job completes. Qdrant `products` = 9 points. 🆕 It's a post-install hook (6.4.10).
  🆕 Verified: `indexed 9 products into Qdrant (hybrid dense+sparse)`; `products` = 9 points, status green
  (read from an api pod); the Job deleted itself on success.
- 🔄 6.6.4 Smoke: `/health`, `/recommend`, `/chat` SSE through the Gateway. **At most 1** live `/aggregate`.
  🆕 Wait for ready EndpointSlices and retry before declaring failure.
  - ✅ 🆕 `make kind-smoke` (`ops/smoke/smoke.py`). devauth **7/7**: web, health, 401 without a token,
    `/recommend`, `/chat` SSE, history stored and deleted (DynamoDB), and 1 live `/aggregate` (3 offers in
    12.4 s; the repeat came from Redis in 0.00 s). clerk **4/4**: a minted HS256 token gets 401. SerpApi
    spend: 1 search.
  - ✅ 🆕 SSE streams through Envoy: first event at 0.09 s of 2.9 s, matching a direct-to-pod run. (The first
    smoke run's SSE parser buffered the stream on the client side; per-event timing found it; fixed.)
  - ✅ 🆕 `make kind-addons` re-run on the live cluster: exit 0 in 47 s, nothing changed (idempotent).
  - ⏳ 🆕 Browser: sign in with Clerk at http://app.localhost and run one search.
- ✅ 6.6.5 Grafana shows api metrics; the `ApiDown` alert fires when api is scaled to 0.
  🆕 Drill: api to 0 → `ApiDown` pending 10 s later → firing at 2 min (its `for`) → Alertmanager → the
  sink logged it; back to 2 replicas (Ready in 6 s) → resolved notification ~2 min later. This only
  works because of F21. Grafana dashboard and Alertmanager screenshots taken (evidence: 6I).

### 6.7 Production-behaviour drills on kind ✅ (correctness, not performance)
🆕 Load: `ops/load/k6-drill.js`, a constant 10 req/s through the Gateway (one token per few requests, so
no user hits the rate limit), failing on any non-200; `MODE=cold` makes every query miss the caches.
- ✅ 6.7.1 **Zero-downtime rollout:** k6 against cached `/recommend` while `helm upgrade` changes the image.
  Error rate should be 0. 🆕 F2 (✅) and the preStop sleep + startup/readiness probes (✅ 6C) are in place.
  🆕 F18 is fixed (6G), so new pods answer in under a second from their first request.
  - ✅ 🆕 Done the GitOps way: new tag committed → Argo CD applied it 6 s later → api and web rolled in 10 s.
    **1800/1800 requests OK**, p95 8.5 ms.
- ✅ 6.7.2 **Rollback:** deploy a broken image tag → readiness fails → `helm rollback` (or Argo CD revert).
  🆕 Broken tag (ErrImageNeverPull) under load: the old pods kept serving, **0 errors** (1801 and 3601 requests).
  The rollback commit first sat unapplied (F29); with a sync timeout it applied by itself ~3.5 min later.
- ✅ 6.7.3 **Self-healing:** `kubectl delete pod` (api) → replaced. `docker stop p2-worker2` → pods rescheduled.
  🆕 Pod delete: replaced in 31 s, **901/901 OK**. Node stop (6 min): marked Unknown after ~50 s, pods evicted
  after the default 300 s and rescheduled. First run **43.1% errors** for the whole outage (F30); after the fix
  **12/4400 (0.27%)**, all in the first ~50 s (the NodePort still sent some connections to the dead proxy).
- ✅ 6.7.4 **Stateful:** delete the Qdrant pod → PVC reattaches, data intact. During the gap, popularity
  fallback serves HTTP 200. 🆕 Caveat: kind's local-path volumes live on one node, so the pod can only
  come back on that node; "survives losing its node" can't be tested on kind (DOKS block storage can).
  🆕 Pod delete: back in 4.5 s on the same PVC, 9 points intact, 359/359 OK (uncached load). Qdrant down
  60 s: **297/297 OK**; the api logged 207 popularity-fallback answers (26 failed retrievals, then the breaker).
- ✅ 6.7.5 **Redis down:** scale to 0 → fast-fail around 0.3 s, not a hang.
  🆕 60 s down under load: **301/301 OK**, median 0.26 s, p90 0.33 s (from ~5 ms). Rate limits fail open (F32).
- ✅ 6.7.6 **HPA:** k6 load → replicas go up and back down (this proves the HPA reacts, not capacity).
  🆕 Capped at 4 on kind. 120 req/s held CPU at 65% (below the 70% target: no scale, correctly). 200 req/s:
  2 → 3 at 61 s, → 4 at 107 s, back to 2 after the 5-min window; **48,001/48,001 OK**.
- ✅ 6.7.7 **Limits:** lower the api memory limit → watch an OOMKill → restore it. Learn the failure signal.
  🆕 Limit 128Mi (request lowered too; a limit below the request is rejected): the new pod was `OOMKilled`,
  exit 137, and the old pods kept serving (361/361 OK). Argo CD self-heal restored 1Gi in 7 s.
- ✅ 6.7.8 **NetworkPolicy:** web → api allowed; a random pod → Redis denied. 🆕 The web pod never calls
  the api directly (same-origin through the Gateway), so test: Gateway → web/api allowed; web → Redis
  and a random pod → Redis denied.
  - ✅ 🆕 **10/10 as designed:** api → Redis/Qdrant/DynamoDB open; web → Redis/api/Qdrant blocked; a pod in
    another namespace → Redis/Qdrant/api blocked; Gateway → web/api HTTP 200.

### 6.8 CI: install test on kind 🔄
- ✅ 🔁 6.8.1 New CI job: `helm/kind-action` + `helm/chart-testing` (`ct lint` + `ct install`). Every PR proves the chart installs.
  🆕 `.github/workflows/kind.yml`: `ct lint`, then a scripted install instead of `ct install` (the chart needs
  a pre-existing Secret and images built in the job): Helm 4.1.4 pinned, a Pod Security `restricted` namespace,
  `--rollback-on-failure --wait=watcher`, then a smoke test. CI values in `ci/kind-values.yaml`.
  - ✅ Validated locally: actionlint 1.7.12 clean; `ct lint` v3.15.0 passes (after F33); the same steps on a
    fresh kind cluster: installed in 116 s, 0 warnings, health OK, 401 without a token, web 200.
  - ⏳ Its first GitHub run (after your push).
- ✅ 6.8.2 Keep it cheap: offline mode, no SerpApi, no LLM keys (dev-auth profile scoped to CI).
  🆕 A dummy dev-auth Secret; with no OpenAI key `/recommend` still answers from the popularity fallback
  (3 products), which the job asserts.

### 6.9 Evidence, runbook, teardown ✅
- ✅ 6.9.1 Save `kubectl get all -n p2`, Argo CD UI, Grafana, and alert-fired screenshots → `assets/screenshots/k8s/`.
  🆕 `cluster-state.txt` (nodes, workloads, HPA/PDB/NetworkPolicies/PVCs, Gateway/route/policy, monitoring
  objects, Argo CD apps, Pod Security labels; no Secret values), `argocd-p2-synced-healthy.png`,
  `grafana-p2-overview.png`, `prometheus-apidown-firing.png`, `alertmanager-apidown-routed.png`,
  `web-sign-in-via-gateway.png`.
- ✅ 6.9.2 Runbook section: "Run on kind" (create → deploy → drills → delete).
  🆕 `docs/runbook-kind.md` (tracked; `Document/` is local-only): from zero, day to day, UIs, drill results,
  what bit and the fixes, memory. The README's deployment section is corrected (no ALB Ingress; Argo CD).
- ✅ 6.9.3 `kind delete cluster --name p2` (🆕 `make kind-down`).
  🆕 Exercised twice, then rebuilt from zero: `make kind-all` **595 s** (smoke 4/4), `make kind-argocd` 97 s,
  43 pods Ready, 5.7 GB. The cluster is left running (clerk profile) for your sign-in.
- **Exit criteria:** one script/Make target goes from no cluster to a smoke-tested app; every drill in 6.7
  passes; the CI kind job is green. 🆕 Lint green for all 3 values files: ✅ already.
  - ✅ 🆕 One target from zero: `make kind-all`. ✅ Every drill in 6.7 passes. ⏳ CI kind job green: after your push.

---

## Phase 7: Non-AWS real managed Kubernetes: DigitalOcean DOKS ⏳ (NEW)

> **Why this phase:** DOKS is a **real, managed, production-grade** Kubernetes service. DigitalOcean
> runs the control plane; your worker nodes are real VMs (Droplets) with real cloud load balancers,
> block storage, DNS and public TLS. It's cheaper and simpler than EKS, so you get the most hands-on
> exposure per dollar. Startups do run production on it.
> **Portability rule:** keep DO-specific parts isolated (Terraform provider, registry, storage class,
> LB annotations, Spaces). Everything else (chart, Gateway, cert-manager, Argo CD, monitoring,
> Velero) is identical on any vendor. If DO credit isn't available, this phase runs nearly
> unchanged on Civo, Linode or GKE (App. B).

### 7.0 Prerequisites & decisions ⏳ (do these first; several need your input)
- ⏳ **7.0.1 Check your credit.** DO Billing → Credits. DO's $200 promo is **for new accounts only and expires
  60 days after it's added**. A credit from "a few months ago" has almost certainly expired, and the
  same account isn't eligible again. Options:
  - **(a) Pay-as-you-go on DO** with a billing alert and tear-down discipline. Recommended; see the cost table below.
  - **(b) Run Phase 7 on a different vendor's new-account credit** (Civo $250, GCP $300/90 days, Linode $100/60 days).
    Only 7.1, 7.2 and the storage class change.
- ⏳ 7.0.2 Set a DO **billing alert** (for example $25) before creating anything.
- ⏳ 7.0.3 Region: **BLR1 (Bangalore)**, the closest DO region to Pakistan, or FRA1. If you keep DynamoDB (7.0.5a),
  pick the nearby AWS region (`ap-south-1` Mumbai for BLR1, `eu-central-1` for FRA1).
- ⏳ 7.0.4 A **domain** (~$10/year), with DNS hosted free on DO. Needed for public TLS and a Clerk production instance.
  No domain? Use `<LB-IP>.sslip.io` for HTTP practice, but a Clerk prod instance and real certificates need your own domain.
- ⏳ **7.0.5 Decision D25: chat-history store.** DynamoDB is AWS-only.
  - **(a) Keep real AWS DynamoDB cross-cloud.** Least-privilege IAM user keys (table-scoped) in a Secret. **Zero code change.** Recommended first.
  - (b) `dynamodb-local` in-cluster. ❌ Not production (no durability or HA). kind only.
  - (c) A Postgres backend (DO Managed PostgreSQL, or the CloudNativePG operator) behind a new `ChatHistory`
    Protocol. About half a day of code + tests. Makes the app cloud-portable. Stretch item **7.10.1**.
- ⏳ 7.0.6 **Langfuse:** use Langfuse Cloud's free Hobby tier instead of self-hosting four stateful services
  (Postgres, ClickHouse, Redis, MinIO). First check that the pinned **v2 SDK still ingests into the
  current Cloud server**. If not, do R3 first, or disable Langfuse for this phase and say so.
- ⏳ 7.0.7 **Clerk:** a dev instance for practice; a production instance needs the 7.0.4 domain + DNS records.
- ⏳ 7.0.8 **SerpApi:** the free tier is 250/month. Budget **≤ 3 live `/aggregate` calls for the whole phase**. Never load-test it.

**Cost plan (approximate; check DO's pricing page):**

| Item | Pricing basis | Practice setup |
|---|---|---|
| Control plane | **Free** (HA control plane +$40/month; skip for practice) | free |
| Worker nodes | Droplet price, **billed per second** | 3 × 2 vCPU / 4 GB ≈ $24/month each |
| Load balancer | Monthly per LB (check the current price) | **1 LB total**: everything goes through the Gateway |
| Block storage | ≈ $0.10/GiB-month | Qdrant + Redis + Prometheus PVCs ≈ 20–30 GiB |
| Container registry (DOCR) | Free starter tier is too small for the ~1.2 GB of images | Basic tier ≈ $5/month |
| Spaces (S3-compatible) | ≈ $5/month minimum | Velero backups + Terraform state |
| **Always-on** | | **≈ $95–110/month** (the $200 credit would have covered ~2 months) |
| **Session-based** (destroy between sessions) | | **≈ $0.15/hour of cluster time + ~$10/month fixed** → 40 hours ≈ **$15–20** |

If kube-prometheus-stack + Argo CD + the app don't fit on 4 GB nodes, move to 2 × 8 GB nodes. Measure first.

### 7.1 Infrastructure as code (DO) ⏳
- ⏳ 7.1.1 New `infra/terraform-do/` using the `digitalocean` provider. Keep it separate from the AWS root.
- ⏳ 7.1.2 Resources: project, VPC, **DOKS cluster** (pinned version, `auto_upgrade = false`, `surge_upgrade = true`),
  node pool `s-2vcpu-4gb` with **autoscaling 2–4**, DOCR registry, Spaces bucket, DNS zone/records.
- ⏳ 7.1.3 Remote state in Spaces (S3-compatible backend) + a state lock strategy.
- ⏳ 7.1.4 `terraform fmt/validate` + `tflint` → **plan review** → `apply`.
- ⏳ 7.1.5 `doctl kubernetes cluster kubeconfig save <name>` → `kubectl get nodes`.
- ⏳ 7.1.6 DO API token stored only in env / password manager. Never in tfvars committed to git.

### 7.2 Registry & images ⏳
- ⏳ 7.2.1 Integrate DOCR with the cluster (registry pull secret in the namespace).
- ⏳ 7.2.2 Build api + web (`linux/amd64`), tag with the git SHA, **Trivy scan** (fail on CRITICAL), then push.
- ⏳ 7.2.3 *(Later)* CI job: build → scan → push to DOCR on tag (mirrors `cd.yml`'s ECR flow).

### 7.3 Platform add-ons, production settings ⏳ (same list as 6.5)
- ⏳ 7.3.1 metrics-server (check whether DOKS already provides it).
- ⏳ 7.3.2 **Envoy Gateway** → its `Service type: LoadBalancer` provisions **one DO load balancer**.
- ⏳ 7.3.3 **cert-manager + Let's Encrypt** (`ClusterIssuer` staging first, then prod). Use DNS-01 via DO DNS or HTTP-01 via the Gateway.
- ⏳ 7.3.4 *(Optional)* **external-dns** (DO provider) so `HTTPRoute` hostnames create DNS records.
- ⏳ 7.3.5 **kube-prometheus-stack** with PVCs + retention; Alertmanager → a **real receiver** (email / Slack / Telegram).
- ⏳ 7.3.6 **Secrets:** SOPS + age (from 6.5.6), or **External Secrets Operator** + a free secrets backend (Doppler / Infisical).
- ⏳ 7.3.7 **Argo CD** (app-of-apps), behind the Gateway with TLS and an admin password rotated after install.
- ⏳ 7.3.8 **Velero** → Spaces (S3-compatible) for namespace + PVC backups.
- ⏳ 7.3.9 *(Optional)* Loki + Alloy for logs with 7–14 day retention. OTel Collector → Jaeger or Tempo.

### 7.4 Deploy the app (GitOps) ⏳
- 🔄 7.4.1 `values-doks.yaml`: `do-block-storage`, DOCR image refs, HTTPRoutes `app.<domain>` / `api.<domain>`, TLS.
  🆕 A skeleton exists (storage class + HPA bound). With the same-origin decision the route is `app.<domain>` with `/api/*` → api, not a separate `api.<domain>` host.
- ⏳ 7.4.2 Secrets for OpenAI, Groq, SerpApi, Clerk, and (7.0.5a) AWS DynamoDB keys, via 7.3.6.
- ⏳ 7.4.3 Argo CD syncs the app. The seed hook Job completes.
- ⏳ 7.4.4 Namespace **Pod Security Admission = `restricted`**; default-deny NetworkPolicies + explicit allows. 🆕 The chart already passes `restricted` (server-side dry run on kind, 6C).
- ⏳ 7.4.5 Resource requests/limits tuned from the kind measurements.

### 7.5 Smoke & close open verifications ⏳
- ⏳ 7.5.1 `https://api.<domain>/health` 200 with a valid Let's Encrypt cert.
- ⏳ 7.5.2 `/recommend`, `/chat` SSE through the Gateway (check that SSE isn't buffered by the proxy).
- ⏳ 7.5.3 **Real Clerk sign-in** in the browser → Discover works → **closes 10.5**.
- ⏳ 7.5.4 One live `/aggregate` → the **Langfuse trace shows tokens + cost** → **closes 11.6 / M-3**.
- ⏳ 7.5.5 (If 7.0.5a) Confirm the `ttl` attribute and TTL enabled on the real DynamoDB table → **closes M-11 live**.

### 7.6 Production drills on a real cluster ⏳
- ⏳ 7.6.1 **Load:** k6 from a **separate Droplet** (or k6-operator) against `/recommend`, `MODE=cached` then
  `MODE=cold` (`mint_tokens 50`). Record p95, error rate and RPS. **Never `/aggregate`.**
- ⏳ 7.6.2 **Autoscaling:** watch HPA add pods **and the node pool add a node**. Record scale-up time.
- ⏳ 7.6.3 **Progressive delivery:** Argo Rollouts canary (closes ✂️ D16) with Prometheus-based analysis,
  or `helm --atomic`. A bad image should auto-abort.
- ⏳ 7.6.4 **Chaos:** delete pods; `kubectl drain` a node (PDBs keep api available); kill Qdrant → popularity fallback; kill Redis → fast-fail.
- ⏳ 7.6.5 **Backup/restore:** Velero backup → delete the namespace → restore. Qdrant snapshot → Spaces → restore. Record RTO/RPO.
- ⏳ 7.6.6 **Alerting:** force `ApiDown` / `HighErrorRate` → receive the notification → resolve.
- ⏳ 7.6.7 **Cluster upgrade:** DOKS minor-version upgrade (surge) while k6 runs. The app stays up.
- ⏳ 7.6.8 **Security:** Trivy-clean policy for CRITICAL, NetworkPolicy deny test, no privileged pods, secrets not in env dumps or logs.

### 7.7 Cost & FinOps ⏳
- ⏳ 7.7.1 Record the actual DO bill for the phase, cost per cluster-hour, and the biggest line item.
- ⏳ 7.7.2 Right-size requests from Grafana data (requested vs actually used).

### 7.8 Runbook ⏳
- ⏳ 7.8.1 "Run on DOKS": create → bootstrap add-ons → deploy → drills → destroy.
- ⏳ 7.8.2 Playbooks: cert renewal failure, LB not provisioning, PVC stuck, node NotReady, Argo CD out-of-sync.

### 7.9 Teardown ⏳ (where people leak money)
- ⏳ 7.9.1 Delete Argo CD apps / `helm uninstall` → **delete PVCs** → delete the Gateway's `LoadBalancer` Service.
- ⏳ 7.9.2 `terraform destroy`.
- ⏳ 7.9.3 **Check the DO dashboard for orphaned Volumes, Load Balancers, snapshots and Spaces.** Resources
  created by Kubernetes controllers can survive a cluster delete and keep billing.

### 7.10 Stretch (optional, maximum exposure) ⏳
- ⏳ 7.10.1 **Postgres history backend:** a `ChatHistory` Protocol + `PostgresChatHistory` + `HISTORY_BACKEND` setting
  + the same isolation/RTBF tests. Run it on the **CloudNativePG** operator (operator pattern, failover,
  backups to Spaces). Makes the app fully cloud-portable.
- ⏳ 7.10.2 **"Hard mode" lab:** `kubeadm` on 3 Droplets (1 control plane + 2 workers). Learn etcd, certificates,
  CNI install and version upgrades (CKA-style). Destroy the same day. This teaches what managed
  Kubernetes hides from you.
- ⏳ 7.10.3 Repeat Phase 7 on **GKE with the $300 GCP credit** and write a DOKS-vs-GKE comparison.

**Exit criteria:** HTTPS app on your domain; real Clerk login; GitOps deploys; alerts reach you; k6
numbers + autoscaling recorded; restore drill timed; teardown leaves $0 running.

---

## Phase 8: Deployment on AWS (EKS) 🔄 (was Phase 6.3–6.6)

> Same chart as Phases 6–7 (`values-eks.yaml`). What's new is the AWS-native layer: IAM for pods,
> VPC networking, ALB, Secrets Manager, ElastiCache, real DynamoDB, and the enterprise-standard
> cost model.

🆕 `values-eks.yaml` exists as a skeleton (gp3 storage class, `alb` ingress class). Phase 8 fills in ECR, IRSA and routing.

### 8.0 Prerequisites ⏳
- ⏳ 8.0.1 AWS account. As of 2026, new accounts get $100 in credits plus up to $100 more for onboarding tasks,
  on a 6-month free plan. The free plan **restricts some services**, so **check that EKS is allowed**;
  you may have to upgrade to the paid plan (the credits still apply).
- ⏳ 8.0.2 **AWS Budgets alarm** at 50% / 100% (also one of the credit-earning tasks).
- ⏳ 8.0.3 An admin role through IAM Identity Center. No root access keys.
- ⏳ 8.0.4 Cost model: EKS control plane ≈ $0.10/hour (~$73/month) + NAT gateway (already `single_nat_gateway = true`) +
  ALB + nodes + ElastiCache. Roughly **$0.25–0.35/hour** with 2 small nodes, **$200+/month if left running**.
  Plan **same-day up/down**.

### 8.1 Terraform plan 🔄
- ✅ 8.1.1 `terraform init && terraform validate`.
- ✅ 8.1.2 A `tfplan` exists locally.
- ⏳ 8.1.3 Enable the S3 + DynamoDB-lock remote backend (`versions.tf:12`).
- ⏳ 8.1.4 `tflint` + `infracost breakdown`. Put the monthly cost into the writeup.
- ⏳ 8.1.5 Review the plan: no public S3, encryption on, PITR on, node sizes as intended.

### 8.2 Dev apply + smoke ⏳ (paid)
- ⏳ 8.2.1 `terraform apply` → `aws eks update-kubeconfig`.
- ⏳ 8.2.2 Push images to ECR (manually, or the first `cd.yml` run).
- ⏳ 8.2.3 Pod identity: IRSA (already in Terraform) **or EKS Pod Identity** (the newer, simpler option) for DynamoDB + Secrets Manager. 🆕 Needs the F7 `history.py` credential fix (6D): today, fake `local` credentials would override IRSA / Pod Identity.
- ⏳ 8.2.4 **ESO + AWS Secrets Manager** → `p2-secrets` (**closes ✂️ D17**).
- ⏳ 8.2.5 North-south: AWS Load Balancer Controller (ALB Ingress), or reuse Envoy Gateway behind an NLB. Same HTTPRoutes. 🆕 ALB Ingress dropped in 6D (it can't be relied
  on to strip `/api`), so: Envoy Gateway behind an NLB.
- ⏳ 8.2.6 Redis → ElastiCache (Terraform module exists); in-cluster Redis disabled in `values-eks.yaml`.
- ⏳ 8.2.7 Same add-ons as 7.3 (Argo CD, kube-prometheus-stack, cert-manager or ACM for TLS).
- ⏳ 8.2.8 Smoke: `/health`, `/recommend`, one `/aggregate`, real Clerk login, live DynamoDB TTL check.
- ⏳ 8.2.9 Evidence: `kubectl get pods`, ALB URL, a Jaeger trace, a Grafana panel, infracost vs actual bill.

### 8.3 Staging: load, resilience, recovery ⏳ (paid)
- ⏳ 8.3.1 k6 (cached + cold) against `/recommend` only; record p95 / errors / RPS; compare with DOKS.
- ⏳ 8.3.2 *(Optional)* **Karpenter** for node autoscaling (the EKS-standard alternative to Cluster Autoscaler).
- ⏳ 8.3.3 Restore drill: **DynamoDB PITR → new table**; Qdrant snapshot → S3 → restore. Time both.
- ⏳ 8.3.4 Alertmanager → real receiver; optionally a CloudWatch billing alarm.
- ⏳ 8.3.5 Cluster chaos: drain a node, kill pods, check degradation.

### 8.4 Prod promote ⏳ (optional for a portfolio)
- ⏳ 8.4.1 First **real `cd.yml` run** (tag `v0.1.0`): OIDC role, GitHub `production` environment. 🆕 Fix §10 D-14 first (`--atomic` deprecated in Helm 4; Helm not pinned in `cd.yml`).
- ⏳ 8.4.2 Rollback test: deploy a broken image → `--atomic` rolls back.
- ⏳ 8.4.3 Dashboards live; alert routing on.
- ⏳ 8.4.4 Honest note: no real users and no on-call. State it; don't imply it.

### 8.5 Teardown & comparison ⏳
- ⏳ 8.5.1 `helm uninstall` → delete PVCs/LBs → `terraform destroy` → check for orphaned EBS volumes, ENIs, ELBs, NAT gateways, CloudWatch log groups.
- ⏳ 8.5.2 Write **"kind vs DOKS vs EKS: what changed"**: IAM, networking, LB, storage, secrets, cost per hour, time-to-cluster.

---

## Phase 9: Portfolio writeup 🔄 (was Phase 7)

`portfolio-writeup.md` exists but describes the **pre-pivot** audio recommender: "83 tests", no
aggregator, no remediation story.

- ⏳ 9.1 Retitle to ProductIQ and lead with the live aggregator. Keep the catalog path as backend [A].
- ⏳ 9.2 New two-backend architecture diagram (catalog Qdrant path + SerpApi aggregator path, one ranker).
- ⏳ 9.3 Results: aggregator **0.9413 / 1.0000 vs Google 0.8240 / 0.8750**; catalog 0.80 / 0.83 / 0.82;
  answer quality 0.94 / 0.65 / 0.56; **121 tests (112 offline + 9 integration)** (🆕 211 after Phase 6: 202 + 9); CVE status.
- ⏳ 9.4 Add the strongest story: *self-audit → 27 findings → 26 fixed, with evidence*
  (C-1 attack transcript before and after; Redis 24.7 s → 0.32 s; no-match fixed).
- ⏳ 9.5 **Deployment journey: kind → DOKS → EKS**, with evidence from each phase (screenshots, k6 numbers,
  autoscaling, restore RTO, real bills). 🆕 6A/6B evidence so far: the NetworkPolicy enforcement
  proof, the 3× allocatable finding, and chart bugs caught before the first install.
- ⏳ 9.6 "What breaks first": the SerpApi quota and per-query costs, not compute. Use the App. A scale guide.
- ⏳ 9.7 Limitations: 4-fixture eval, faithfulness 0.56, M-12, no real users, no on-call.
- ⏳ 9.8 Decide where it's published. `Document/` is gitignored, so a public writeup must live
  somewhere else (a README section, `docs/case-study.md`, a blog or LinkedIn).

---

## 10. Drift & bugs found today

| # | File | Problem | Fix | Effort |
|---|---|---|---|---|
| D-1 | [README.md:640](../../README.md#L640), [README.md:659](../../README.md#L659) | History key is shown as `PK=USER#{id}#SESSION#{sid}`, `SK=MSG#…`. The code (`packages/core/history.py`) uses `PK=USER#{user_id}`, `SK=SESSION#{sid}#MSG#{nanos}#{rand}`. That one-partition-per-user layout is *why* RTBF is a single-partition delete | Correct both blocks | 5 min |
| D-2 | [README.md:680](../../README.md#L680) | Says **117** (108 offline + 9 integration). Actual: **121 (112 + 9)**; 🆕 **211 (202 + 9)** after Phase 6 | Update the number, or make it generic ("run `--collect-only`") so it can't drift again | 2 min |
| D-3 | [README.md:449](../../README.md#L449) | "all **15** services". Lines 316 and 403 say **16** | Change to 16 | 1 min |
| D-4 | [README.md:113](../../README.md#L113) | Links `assets/screenshots/redis_cache.png`. The tracked file is `Redis_cache.png`. GitHub is case-sensitive, so **the image is broken on GitHub** (fine on Windows) | `git mv assets/screenshots/Redis_cache.png assets/screenshots/redis_cache.png` | 1 min |
| D-5 | [pricing/page.tsx:8-25](../../apps/web/app/pricing/page.tsx#L8-L25), [PricingPlans.tsx:19-68](../../apps/web/components/PricingPlans.tsx#L19-L68) | The banner says "demo", but the copy states product facts that are false: "**Unlimited** AI searches" (global budget is 40/day), "**Llama 3.1**" (actually `llama-3.3-70b`), "**Cross-encoder reranking**" on Pro (`rerank_enabled=False`), 14-day trial / refunds / proration, SSO/SAML, fine-tuning, data residency, API access, SLA | Either remove `/pricing`, or rewrite it as "Illustrative pricing: none of these tiers exist", with features limited to what the backend does | 20 min |
| D-6 | `Document/docs/hardening.md` | Claims a Trivy CI job, bandit in CI, and ESO. None exist | Rewrite (§5.1) or build them (§5.2–5.3) | 15 min |
| D-7 | [.gitignore:41-48](../../.gitignore#L41-L48) | Comment says "Screenshots are not published", but 13 are tracked (re-captured 08-01, after the cleanup) | Update the comment | 1 min |
| D-8 | [README.md:100](../../README.md#L100) | Langfuse caption claims "per-request LLM cost". Never live-confirmed after M-3 | Confirm (7.5.4), or soften the caption | 5 min |
| D-9 | `Document/docs/portfolio-writeup.md` | Pre-pivot: 83 tests, no aggregator | Phase 9 | 1–2 h |
| D-10 | `Document/docs/remediation-report.md` (m-11) | Says `docs/` was un-ignored. Now all of `Document/` is ignored; only `docs/decision-log.md` + `reports/` are tracked | One-line note (local doc) | 1 min |
| D-11 | git history | The last 5 commits are titled `docs ...` | Going forward, use descriptive messages. **Don't rewrite pushed history**. 🆕 Applied from the Phase 6 session on | — |
| 🆕 D-12 | `tests/integration/test_history.py` | Its 5 tests have no `integration` marker, so the "offline" suite runs them and they silently skip when DynamoDB-local is down. §12's "offline, no services" count quietly needs `make db` | Add the marker, or cover the same logic with a faked DynamoDB in a unit test | 10 min |
| 🆕 D-13 | `.env`, Step 6.5, D19 | `ANTHROPIC_API_KEY` is now set, so "the Anthropic leg was never called live (no key)" and "the judge is gpt-4o because there's no Anthropic key" are stale | Make one live fallback call to close 6.5; decide whether to move the judge off-family | 15 min |
| 🆕 D-14 | `.github/workflows/cd.yml:50-56` | `helm upgrade --install ... --wait --atomic`: `--atomic` is deprecated in Helm 4 (use `--rollback-on-failure`), and `cd.yml` doesn't pin Helm, so the runner image decides v3 vs v4 | Pin Helm with `azure/setup-helm`; switch to `--rollback-on-failure` once on Helm 4 | 10 min |
| 🆕 D-15 | `Makefile` (`wait-api`, `urls`, `upv`, `full`, `bootstrap`) | Their recipes use sh syntax (`set -a; . ./.env`, `$$(seq …)`). Run from PowerShell, GNU make finds no sh.exe and uses cmd.exe, so they fail (F19; inferred from the 6E probe, not run) | Run them from Git Bash, or move the logic into a script like the kind targets | 15 min |

---

## 11. Roadmap (from README) with sub-steps

- ⏳ **R1 Apply the Terraform.** Same as Phase 8.
- ⏳ **R2 End-to-end tests**
  - ⏳ R2.1 Add Playwright to `apps/web`. Call it as `node node_modules/@playwright/test/cli.js`, because the `&` in the repo path breaks npm `.cmd` shims.
  - ⏳ R2.2 Mock `/aggregate/stream` from the recorded fixture: **0 SerpApi spend**.
  - ⏳ R2.3 Specs: cards render before the reasons; cancel mid-stream; `no_match` banner; `source_unavailable` banner; signed-out redirect.
  - ⏳ R2.4 Add an `e2e` job to `ci.yml`. Later, run the same specs against the kind deployment (6.8).
- ⏳ **R3 LangChain 0.3 → 1.x + Langfuse 2 → 3**
  - ⏳ R3.1 Branch. Bump `langchain*` and `langfuse`.
  - ⏳ R3.2 Fix imports (`langchain.callbacks.base`, callback handler API).
  - ⏳ R3.3 Full suite + both eval gates.
  - ⏳ R3.4 **One live query → confirm the Langfuse trace exists, with tokens and cost.** Tracing breaks silently, so tests alone don't prove it works.
  - ⏳ R3.5 Delete the 6 `--ignore-vuln` lines → `pip-audit` green with no ignores.
- ⏳ **R4 Broaden the catalog.** Multi-category data so Recall@k means something. Re-baseline Step 5.
- ⏳ **R5 Lift faithfulness above 0.56**
  - ⏳ R5.1 Make citations mandatory (every reason must quote evidence IDs).
  - ⏳ R5.2 Widen the context window.
  - ⏳ R5.3 `make eval-rag` → new baseline. Add a faithfulness floor to the local gate.
- ⏳ **R6 Re-open the reranker.** Title-level reranking, then re-A/B. Keep it off unless NDCG@3 improves.
- ⏳ **R7 Agentic tools.** `filter_by_price` / `compare_products` via LangGraph, with an eval of the tool-call path.
- ⏸️ **R8 vLLM on a GPU pool.** Only once sustained traffic justifies it (≈ 10M-MAU tier, App. A).
- ⏳ **R9 Slim the API image.** Sparse-embedding microservice + `python:3.13-slim` (closes M-12).

---

## 12. Verify it yourself

Offline, $0, no SerpApi spend:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages apps tests ops infra       # 🆕 ops/ and infra/ added in 6E
uv run pytest -q -m "not integration"            # 🆕 202 offline tests. Without DynamoDB-local:
                                                 #    197 passed + 5 skipped (§10 D-12)
uv run pytest --collect-only -q                  # 🆕 expect 211 tests collected
uv run python -m evaluation.aggregator.gate      # expect PASS (beats Google order)
make helm-lint                                   # 🆕 kind 27, doks/eks 21 resources, all valid (HTTPRoute via the CRD catalog) (helm + kubeconform)
make alerts-test                                 # 🆕 promtool: 10 rules valid + 4 ApiDown unit tests (Docker)
cd infra/terraform && terraform validate         # no apply
cd apps/web && node node_modules/typescript/bin/tsc --noEmit
```

With services up (`make upv`, needs Docker + keys in `.env`):

```bash
uv run pytest -q -m integration                  # 9 tests
make eval-gate                                   # catalog gate (seeded Qdrant + OPENAI_API_KEY)
make urls                                        # Jaeger / Prometheus / Grafana / Langfuse links
```

Phase 6 (🆕 end to end on kind; details in docs/runbook-kind.md):

```bash
make kind-all                                    # 🆕 from no cluster to a smoke-tested app (595 s measured)
make kind-argocd                                 # 🆕 hand it to Argo CD (97 s); then deploy with: make kind-images kind-gitops
make kind-up                                     # 🆕 create the cluster (make kind-down deletes it)
make kind-addons                                 # 🆕 metrics-server, Envoy Gateway, cert-manager, Gateway, CA (re-runnable)
make kind-images                                 # 🆕 api + web at <sha>[-dirty], loaded into the nodes
make kind-secret PROFILE=devauth                 # 🆕 Secret from a filtered .env (clerk | devauth); restarts the api
make kind-deploy                                 # 🆕 helm upgrade --install --rollback-on-failure --wait=watcher
make kind-smoke PROFILE=devauth                  # 🆕 6 checks through the Gateway; AGGREGATE=1 adds 1 SerpApi search
kubectl get nodes                                # 3 Ready
kubectl get pods -n p2                           # 7 Running: 2 api, 2 web, qdrant, redis, dynamodb
kubectl get hpa,pdb,networkpolicy -n p2
```

---

## Appendix A: Scale guide, 10k → 10M+ users (for this project)

**Assumptions** (adjust them; the shape of the answer holds): DAU = 10% of MAU · 5 searches per DAU
per day · peak = 4× average · cache hit 60% (so 40% of searches pay for SerpApi + an LLM call) · about
3 API requests per search · LLM ≈ 1,500 input + 250 output tokens on Groq `llama-3.3-70b`
($0.59 / $0.79 per M tokens ≈ **$0.0011 per call**) · SerpApi list prices as of Oct 2026.

| Tier (MAU) | Searches/day | Peak searches/s | Peak API RPS | Paid SerpApi searches/month | SerpApi cost/month | LLM cost/month |
|---|---|---|---|---|---|---|
| **10k** | 5k | ~0.25 | < 1 | ~60k | ~$725 ("Searcher" 100k plan) | ~$65 |
| **100k** | 50k | ~2.3 | ~7 | ~600k | ~$3,750 (1M "Cloud" tier) | ~$660 |
| **1M** | 500k | ~23 | ~70 | ~6M | ≈ $15–20k (interpolated Cloud tiers) | ~$6.6k |
| **10M+** | 5M+ | ~230+ | ~700+ | ~60M+ | > $106k (past the largest published tier) | ~$66k+ |

**The honest headline:** compute is the *cheap, easy* part at every tier. Even 10M MAU is only
~700 API RPS at peak, which a modest Kubernetes cluster serves. What actually limits this
product is **per-query cost**: the paid data source plus the LLM. With today's SerpApi **free** plan (250/month,
≈ 8 uncached searches a day), the product can't serve even the 10k tier. **Scaling this product
means improving cache hit rate, data-source economics and model routing first; cluster size
comes second.** The README's 200 RPS NFR corresponds to roughly 3M MAU under these assumptions.

### What the right architecture looks like at each tier

**10k MAU (startup, pre-revenue)**
- Platform: **one small managed Kubernetes cluster (2–3 nodes, single region)**, or honestly a PaaS / single VM.
  Kubernetes is optional at this size; you'd use it here for practice and future-proofing.
- Data: managed DB, in-cluster Qdrant + Redis are fine. Daily backups.
- Ops: GitOps, basic alerts, a weekly restore test. No on-call rotation.
- Biggest lever: raise the cache hit rate (popular-query pre-warming, longer TTL for stable categories).
- *This project after Phase 7 is roughly this tier's infrastructure.*

**100k MAU (early scale-up)**
- Platform: managed Kubernetes, **multi-AZ**, 3–6 nodes, HPA + node autoscaling, **separate node pools** (system / app / stateful).
- Data: managed Redis with a replica, Qdrant with replicas (or Qdrant Cloud), managed history DB with PITR. CDN for the web app.
- Ops: SLOs (for example 99.5%) with burn-rate alerts, an on-call rotation (even 2 people), canary deploys, load tests in CI.
- Biggest levers: **start building your own catalog** (merchant feeds / affiliate APIs) to cut SerpApi spend;
  cache LLM explanations per (query cluster, product set).

**1M MAU (scale-up)**
- Platform: multi-AZ Kubernetes with **Karpenter / cluster autoscaler**, PDBs everywhere, WAF + edge rate limiting, a CDN.
- Data: **your own product index** (ingestion pipeline + Qdrant cluster, sharded + replicated). SerpApi only as a fallback.
  Redis cluster, history DB tuned (on-demand DynamoDB / partitioned Postgres).
- LLM: **model routing** (small model for simple queries, 70B only when needed; closes ✂️ D20), prompt caching, provider fallback.
- Ops: platform/SRE team (2–4 people), disaster-recovery plan with tested RTO/RPO, FinOps dashboards, chaos testing.
- Product: real interaction data → **actual personalisation** (collaborative filtering), experimentation (GrowthBook; closes ✂️ D19 flags).

**10M+ MAU (enterprise)**
- Platform: **multi-region** (active-active or active-passive), global load balancing / anycast, **cell-based**
  architecture (each region or cell is an independent copy of the stack), multi-cluster GitOps (Argo CD ApplicationSets).
- Data: streaming ingestion (Kafka) for price/stock updates, a data warehouse + feature store, a multi-region
  history store (DynamoDB global tables / Spanner / CockroachDB).
- LLM: **self-hosted inference (vLLM on GPU node pools; roadmap R8)** once the API bill (~$66k+/month) is more than the cost of running GPUs.
- Ops: 24/7 SRE on-call, incident management, compliance (SOC 2, GDPR DPAs), a dedicated security team.

---

## Appendix B: Kubernetes vendors (checked 2026-10-06; promos change, re-check before signing up)

### Free credits that fit your learning plan

| Vendor | Managed Kubernetes | New-account offer | Notes for you |
|---|---|---|---|
| **DigitalOcean** | DOKS | **$200 / 60 days, new accounts only** | Free control plane (HA +$40/month), per-second node billing, BLR1 region near Pakistan. Your old credit has most likely expired |
| **Civo** | Civo Kubernetes (k3s / Talos based) | **$250** | Fastest cluster creation (~1–2 min), good for repeated practice. Check the credit's expiry |
| **Akamai (Linode)** | LKE | **$100 / 60 days** | Free control plane; simple |
| **Vultr** | VKE | **$100 / 14 days** (some promos $300 / 30 days) | Shortest trial window |
| **OVHcloud** | Managed Kubernetes | ~CA$270 cloud-native trial | EU-focused; free control plane |
| **Google Cloud** | **GKE** (Standard / Autopilot) | **$300 / 90 days** | Widely considered the most polished managed Kubernetes. Longest-lasting credit. Best second cloud after DO |
| **Microsoft Azure** | **AKS** | **$200 / 30 days** + 12 months of selected free services | Free-tier control plane; strong in enterprises |
| **AWS** | **EKS** | $100 + up to $100 (tasks), 6-month free plan | Check EKS eligibility on the free plan; control plane ≈ $73/month |
| **Oracle Cloud** | **OKE** | Always Free Arm (A1) compute: **cut to 2 OCPU / 12 GB in June 2026** | Basic cluster control plane is free; nodes are **arm64**, so you'd need multi-arch images (`docker buildx`). Good for a long-running free lab |

**Suggested order for most exposure per dollar:** kind ($0) → **DOKS** (pay-as-you-go ≈ $15–40 with
teardown, or Civo's $250) → **GKE** ($300 / 90 days) → **EKS** (AWS credits, same-day up/down).
Card payments: some vendors reject some Pakistani cards. DigitalOcean also accepts PayPal.

### Who uses what

| Segment | Most common choices | Why |
|---|---|---|
| **Startups** | DigitalOcean DOKS, Civo, Linode LKE, GKE Autopilot; Hetzner + self-managed k3s/Talos (cheapest compute); often a PaaS instead of Kubernetes (Render, Railway, Fly.io, Cloud Run, Vercel for frontends) | Simplicity and low fixed cost. Many teams don't need Kubernetes until ~100k users |
| **Scale-ups** | **EKS, GKE, AKS**, usually funded by startup credit programs (AWS Activate, Google for Startups Cloud Program, Microsoft for Startups) | Managed data services, IAM, compliance, hiring pool |
| **Enterprises** | **EKS, AKS, GKE**; **Red Hat OpenShift** (incl. ROSA on AWS / ARO on Azure / on-prem); SUSE **Rancher / RKE2**; VMware Tanzu; Mirantis; regional clouds (Alibaba ACK, Tencent TKE in China) | Hybrid / on-prem, governance, vendor support contracts, multi-cluster fleet management |
| **AI / GPU-heavy** | CoreWeave, Nebius, Lambda, Crusoe (Kubernetes-native GPU clouds); inference platforms (Together, Fireworks, Baseten) | GPU availability and price for self-hosted inference (R8) |
| **Self-managed (learning / edge / on-prem)** | kubeadm (CKA standard), k3s, RKE2, Talos Linux, k0s, MicroK8s | Teaches what managed control planes hide; used on bare metal and at the edge |

**Career angle:** EKS, GKE and AKS dominate job descriptions. DOKS teaches the same Kubernetes concepts
for less money. The Phase 7 → 8 sequence gives you both, plus a written comparison (8.5.2), which is a
good interview talking point.
