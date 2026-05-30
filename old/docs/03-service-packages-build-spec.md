# Service Packages and Production Build-Spec

> Input = the gap analysis + tech list from `01-career-assessment.md` and `02-market-positioning.md`. This is a reference document, not linear reading. Opinionated defaults; "it depends" only with a default + the trigger that flips it.

---

# PART A — Service Package Catalogue

Seven packages inside your realistic post-gap envelope. The first three are yours; four added.

### 1. Production-grade RAG application
End-to-end retrieval-augmented chat/search system: frontend + backend + RAG core + deploy (Docker/K8s/Terraform/CI-CD) + observability/eval/cost controls, built to scale.
- Internal knowledge assistant for a 5,000-employee company over Confluence + Google Drive + Slack history.
- Customer-support deflection bot over a SaaS product's docs + past tickets, embedded in their help widget.
- Policy/contract Q&A assistant for an insurance firm over thousands of PDF policies with citations.

### 2. Production-grade Agentic AI application
Multi-step, tool-using agent system (single or multi-agent) with planning, memory, and guardrails, productionized to the same scope as #1.
- Research-and-report agent that browses, queries internal DBs, and produces sourced briefs for an analyst team.
- Operations agent that triages inbound emails, calls internal APIs, and drafts/sends actions with human-in-loop approval.
- E-commerce shopping agent that searches catalog, compares, checks inventory APIs, and assembles carts.

### 3. Production-grade fine-tuned LLM application
A domain-tuned (LoRA/QLoRA/full) model trained on client data, served behind an API with the full production stack.
- Brand-voice content generator fine-tuned on a company's marketing corpus.
- Domain classifier/extractor (e.g., clinical note → structured fields) fine-tuned for accuracy a prompt can't reach.
- Code-assistant fine-tuned on a company's internal SDK/framework conventions.

### 4. Document Intelligence pipeline
High-throughput ingestion → parse → extract → structure → index pipeline for documents (often the data backbone under a RAG app, sold standalone).
- Invoice/PO/receipt extraction at scale for a finance team, output to their ERP.
- Contract clause extraction + risk flagging for a legal ops team.
- Resume/CV parsing + ranking pipeline for a recruiting platform.

### 5. AI microservice into an existing system
A self-contained GenAI capability dropped into a client's existing app as a service/API — lowest-risk, highest-demand entry point.
- "Summarize this thread" + "smart reply" microservice added to an existing support tool.
- Semantic search endpoint added to an existing product catalog.
- Auto-tagging/classification microservice behind an existing CMS.

### 6. Multi-modal AI application (vision + voice + text)
App combining image/audio with text — leveraging your ViT/segmentation/Whisper/TTS/OpenCV exposure.
- Voice assistant: speech-in (Whisper) → reasoning → speech-out (TTS) for a hands-free field-service app.
- Visual QA: upload a product photo, get identification + spec answers (vision model + RAG).
- Medical/industrial image triage with a text report generator (classification/segmentation + LLM narrative).

### 7. LLM Evaluation & Observability platform
Instrumentation, eval harness, and dashboards that make *someone else's* LLM app measurable, testable, and cost-controlled. Sells precisely because it's the gap most teams have.
- Drop-in eval + tracing for a startup whose RAG bot "sometimes hallucinates" but has no metrics.
- Regression-gating CI for a team shipping prompt changes blind.
- Cost + latency dashboard with alerting/kill-switches for a team bleeding token spend.

---

# PART B — Full Build-Specs

> Conventions used below: **DB default Postgres**, **vector default pgvector (small) / Qdrant (scale)**, **backend default FastAPI (Python)**, **frontend default Next.js**, **cloud default AWS**, **orchestration default EKS for scale / ECS Fargate for simpler**, **IaC default Terraform**, **CI default GitHub Actions**, **LLM-obs default Langfuse**. Each package restates only where it diverges.

---

## PACKAGE 1 — Production-grade RAG application

**1. Definition and target use cases.** End-to-end RAG chat/search at scale. Use cases: 5k-employee internal assistant over Confluence+Drive+Slack; support-deflection bot over docs+tickets; insurance policy Q&A with citations.

**2. Frontend layer.**
- Framework: **Next.js (App Router)** — default. Alt: **SvelteKit** (lighter, swap if team prefers Svelte / minimal bundle); **Streamlit** only for internal-tools/MVP.
- UI: **shadcn/ui + Tailwind**. State: **TanStack Query + Zustand** (server cache + light client state; Redux only if app state gets genuinely complex).
- Auth UI: hosted widget from the auth provider (see §9). Streaming UX: **SSE token streaming** with a stop/cancel button (AbortController), retry-on-failure, optimistic user-message echo, skeleton/typing indicator, and **render citations as the answer streams**.

**3. Backend layer.**
- **FastAPI (Python)** — default (matches your stack, async, ecosystem). Alt: **Litestar** (more structure at scale); **NestJS** only if client is Node-shop.
- Async: `async`/`await` end-to-end, `httpx.AsyncClient`, stream LLM tokens through to SSE. API style: **REST** (GraphQL/gRPC unnecessary here).
- Background jobs: **Celery + Redis** for ingestion/re-index (alt: **ARQ** lighter, **SQS+worker** AWS-native). Schemas: **Pydantic v2** request/response. Rate limiting: per-API-key + per-user token bucket (SlowAPI / Redis).

**4. AI/ML core.**
- Providers/model strategy: **tiered** — cheap default (GPT-4o-mini / Claude Haiku / Llama-3.1-8B on Groq), escalate to a strong model (Claude Sonnet / GPT-4o) on low retrieval confidence or long/complex queries. Self-host (vLLM) only at high, steady volume where API cost dominates.
- Orchestration: **LangGraph** for anything with branching/agentic-RAG; **plain LCEL / thin custom** for naive RAG. Reasoning: you know LangChain; LangGraph gives explicit, debuggable state. Avoid heavy framework lock-in for simple flows.
- Prompt management: prompts in version-controlled files + **Langfuse prompt management** for runtime versioning/rollback.
- RAG specifics: **chunking** — recursive/structure-aware ~500–800 tokens, 10–15% overlap; semantic chunking for heterogeneous docs. **Embeddings** — `text-embedding-3-large` (default) or `bge-large`/self-host to cut cost. **Retrieval** — **hybrid (dense + BM25) + reranker** (Cohere Rerank or `bge-reranker`); start dense-only, add hybrid+rerank when eval shows recall gaps. **Context construction** — dedup, MMR for diversity, citation metadata, token-budget-aware packing.

**5. Data layer.**
- Vector DB: **pgvector** (default; one fewer system, transactional with metadata) → **Qdrant** when you need >~5–10M vectors, heavy metadata filtering, or horizontal scale (alt: Pinecone if you want fully-managed-no-ops; OpenSearch if hybrid+logs already there).
- Primary DB: **Postgres** (users, conversations, documents, audit). Cache: **Redis** (sessions, semantic+response cache). Queue: **Redis/Celery** or **SQS**. Blob: **S3** (raw docs). Search index: covered by hybrid in vector layer or OpenSearch.

**6. Infrastructure and deployment.**
- Docker: multi-stage, slim base, pinned deps, non-root, separate ingestion-worker image; no model weights baked in for API-based RAG.
- Orchestration: **EKS** for scale (default for this package) with HPA on CPU+custom latency metric; **ECS Fargate** if the client wants less ops. GPU node pool only if self-hosting embeddings/LLM.
- IaC: **Terraform**, module-per-concern (network, data, eks, app, observability), remote state in S3+DynamoDB lock, per-env workspaces.
- AWS services: VPC, EKS/ECS, RDS Postgres, ElastiCache Redis, S3, ALB, ACM, Secrets Manager, CloudWatch. Inference serving: **provider API by default**; **vLLM on EKS GPU** or **Bedrock** when self-hosting/compliance demands it; SageMaker if client is already SageMaker-centric.

**7. CI/CD and version control.**
- Git: trunk-based with short-lived PR branches. Repo: **monorepo** (frontend/backend/infra/eval). Pipeline: **GitHub Actions** — lint → unit → integration → **RAG eval gate (RAGAS)** → build/push image → deploy dev → manual gate → staging → prod. Prompt/model versioning via Langfuse + git tags. Promotion: image-digest promotion across envs; rollback = redeploy previous digest + Helm rollback.

**8. Observability.**
- App: **OpenTelemetry** → **Grafana stack (Tempo/Loki/Prometheus)** or Datadog. LLM: **Langfuse** (default — open-source, self-hostable, traces every retrieval+generation step, token/cost, prompt versions). Alt: LangSmith (if all-LangChain), Arize Phoenix (eval-heavy), Helicone (proxy-simple). Track: per-request token/cost, retrieval latency vs generation latency, groundedness/eval-in-prod sampling, cache hit rate.

**9. Security and compliance.**
- AuthN: **Cognito** (AWS-native default) / Clerk / Auth0. AuthZ: RBAC + per-document ACL filtering at retrieval (critical for internal-KB use cases — never retrieve docs a user can't see). Secrets: AWS Secrets Manager + KMS. PII: redact at ingestion + log scrubbing. Prompt-injection: input/output guardrails (Llama Guard / regex + LLM classifier), strip retrieved-content instructions. Audit logging for every query+doc-access. Rate limit + WAF.

**10. Scaling for millions of users.**
- Caching: **semantic cache** (embed query, return cached answer on high similarity) + response cache + embedding cache. Model routing/tiering (cheap-first). Streaming default; batch only for offline re-index. Queue depth managed for ingestion. Multi-AZ; CloudFront for static + cacheable answers.
- **Bottleneck checklist (breaks first → fix):** (1) vector search latency/throughput → Qdrant + replicas + filtering pushdown; (2) embedding API rate limits on ingestion → batch + self-host embeddings; (3) LLM provider rate limits/cost → tiering + semantic cache + multiple keys/regions; (4) Postgres connections → PgBouncer; (5) re-index downtime → blue-green collection swap.

**11. Cost controls.** Per-request + per-user/tenant token budgets; cheap-model default; semantic+response cache (biggest lever); batch embeddings; spend dashboards + alerts (Langfuse + CloudWatch); hard kill-switch env flag to drop to cheapest model or shed load.

**12. Testing and evaluation.** Unit (chunking, retrieval filters, prompt builders); integration (ingest→retrieve→answer); e2e (Playwright). **LLM eval:** golden Q/A set with ground-truth contexts; **RAGAS** (faithfulness, answer-relevancy, context-precision/recall) in CI as a gate; online eval sampling + thumbs feedback; A/B prompts/models via Langfuse. Load test: **k6** to find RPS ceiling + p95/p99.

**13. Reference project structure.**
```
rag-app/
├── frontend/            # Next.js app (chat UI, streaming, citations)
├── backend/
│   ├── app/
│   │   ├── api/         # routes: chat, ingest, health, admin
│   │   ├── rag/         # chunking, embeddings, retrieval, rerank, prompt
│   │   ├── core/        # config, security, rate_limiter, guardrails
│   │   ├── observability/  # otel, langfuse, cost_tracker
│   │   ├── schemas/     # pydantic request/response
│   │   └── workers/     # celery ingestion/re-index tasks
│   └── tests/{unit,integration,evaluation}/
├── infra/
│   ├── terraform/       # modules: network, data, eks, app, observability
│   ├── k8s/ (or helm/)  # manifests/charts, hpa, secrets, network-policy
│   └── monitoring/      # prometheus, grafana dashboards
├── eval/                # golden_dataset.json, ragas runner
├── load_tests/          # k6 scripts
├── .github/workflows/   # ci.yml, rag-eval.yml, cd.yml
└── docker-compose.yml   # local full stack
```

**14. Production hardening checklist.** Secrets externalized (no `.env` in image/repo); non-root containers + image scan (Trivy); per-doc ACL enforced in retrieval; rate limiting + WAF live; structured logs with PII scrubbing + retention policy; OTel traces + Langfuse live; RAGAS gate in CI; HPA + PodDisruptionBudget + resource limits; readiness/liveness probes; DB backups + restore tested; semantic cache live; cost alerts + kill-switch; load-tested to target RPS with p95/p99 recorded; runbook + on-call alerts; graceful degradation when provider/vector DB down; right-to-be-forgotten path.

**15. Transformation roadmap (portfolio → production).**
1. Add config/secrets management + `.env.example`; remove hardcoded keys; pin dependencies.
2. Restructure into `backend/app/{api,rag,core,observability,schemas}` modules; add Pydantic schemas.
3. Add structured logging + custom exceptions + request IDs.
4. Add health/readiness endpoints + graceful shutdown.
5. Swap ad-hoc vector usage to abstracted retriever; make embedding/vector backends configurable (pgvector default).
6. Add hybrid retrieval + reranker behind a feature flag.
7. Add Langfuse tracing on every retrieval+generation; capture tokens/cost.
8. Build golden dataset + RAGAS runner; run locally.
9. Add unit + integration tests; wire CI (lint→test→eval gate).
10. Add Redis: sessions + response cache, then semantic cache.
11. Add auth (Cognito/Clerk) + per-user/doc ACL filtering in retrieval.
12. Add rate limiting + input/output guardrails (prompt-injection).
13. Add model tiering + cost budget enforcement + kill-switch.
14. Containerize properly (multi-stage, non-root, Trivy scan); docker-compose full stack.
15. Move ingestion to Celery worker; add blue-green re-index.
16. Write Terraform modules (network, data, eks, app); remote state.
17. Deploy to EKS with Helm: HPA, PDB, probes, network policy, secrets.
18. Add OTel → Grafana/Tempo; dashboards + alerts + cost alerts.
19. k6 load test; tune HPA + connection pooling; record p95/p99.
20. Write runbook, README, architecture diagram; backup/restore drill.

---

## PACKAGE 2 — Production-grade Agentic AI application

**1. Definition and use cases.** Tool-using multi-step agent(s) productionized. Use cases: research-and-report agent; ops email-triage agent with human-in-loop; e-commerce shopping agent.

**2. Frontend layer.** Same base as P1 (Next.js + shadcn). Divergence: **agent-run UX** — stream *intermediate steps* (tool calls, reasoning, tokens) via SSE with a collapsible "agent trace" panel; **human-in-loop approval UI** (approve/edit/reject a proposed action); cancellation must abort the whole run, not one step; show per-step status and final result with provenance.

**3. Backend layer.** FastAPI. Divergence: agent runs are **long-lived** → run them as **background jobs** (Celery/ARQ) with a run-state store and SSE/websocket to stream progress; idempotency keys per run; per-run timeout + max-step/loop guard. REST + SSE.

**4. AI/ML core.**
- Model strategy: strong model for planning/tool-selection (Claude Sonnet / GPT-4o), cheap model for sub-steps; tiering matters more here because agents multiply calls.
- Orchestration: **LangGraph** (default — explicit state graph, checkpointing, human-in-loop interrupts, durable). Alt: **custom thin loop** for single-tool agents (avoid framework overhead); CrewAI/AutoGen only for genuinely multi-agent collaborative use cases.
- Agent specifics: **ReAct** for single-agent tool use; **plan-and-execute** for long tasks; **orchestrator-worker / supervisor** multi-agent only when roles are truly distinct. Tool/function-calling with strict JSON schemas + validation; **memory** = short-term (run state) + long-term (vector/episodic store); **durable execution + checkpointing** so a failed run resumes; **cost/loop guards** (max steps, max spend per run).

**5. Data layer.** Postgres (runs, steps, audit, approvals) — the **run/step state store is central here**. Redis (run cache, locks, rate limit). Vector DB (agent long-term memory + any RAG tools). S3 (artifacts agents produce). Queue: Celery/SQS for run execution.

**6. Infrastructure.** Same AWS/EKS/Terraform base as P1. Divergence: worker pool sized for concurrent long-running agent runs (CPU-bound waiting on tool/LLM I/O → many lightweight async workers); separate HPA on queue depth, not just CPU.

**7. CI/CD.** Same as P1. Divergence: eval gate is **agent-trajectory eval** (did it pick right tools, finish, stay in budget) not just answer quality; replay recorded traces in CI.

**8. Observability.** **Langfuse** shines here — trace every step/tool-call/decision with latency+cost per step. Add: tool-success rate, average steps-per-run, runs-hitting-loop-guard, cost-per-run distribution, human-approval rates. OTel for the service layer.

**9. Security and compliance.** **Highest-risk package** — tools can act on the world. Mitigations: **tool sandboxing + least-privilege** (each tool scoped to minimal perms/credentials); **human-in-loop for destructive/irreversible actions**; allowlist of callable tools per user/tenant; output + action filtering; prompt-injection defense is critical (injected text can hijack tool use → strip/validate retrieved content, constrain tool args); full audit log of every action taken; rate + spend limits per run/user.

**10. Scaling for millions of users.** Run-level concurrency control + queue leveling (agents are expensive — backpressure is essential). Cache deterministic tool results; cache sub-answers. Tier models aggressively. Per-tenant concurrency quotas to prevent noisy neighbors.
- **Bottleneck checklist:** (1) runaway loops/cost → step+spend guards (do first); (2) worker pool saturation under concurrent runs → autoscale on queue depth; (3) tool/external-API rate limits → per-tool throttling + retries with backoff; (4) LLM cost explosion → tiering + caching + budgets; (5) state store contention → Postgres + Redis locks, partition by run.

**11. Cost controls.** Per-run hard budget + max steps (the #1 control); model tiering per step; cache tool results + sub-answers; spend alerting per tenant; kill-switch to disable expensive tools/agents under budget pressure.

**12. Testing and eval.** Unit (each tool, arg validation, guards); integration (full run on fixtures with mocked tools); **trajectory eval** (golden tasks: success rate, steps, cost, correct tool selection) in CI; online eval + human review sampling; load test concurrent runs with k6.

**13. Reference project structure.** As P1 but `backend/app/` has `agents/` (graph definitions, nodes), `tools/` (each tool + schema + perms), `runs/` (state store, executor), `memory/`; `eval/` holds `trajectories/` golden tasks.

**14. Production hardening checklist.** All of P1's, plus: per-tool least-privilege creds; human-in-loop on irreversible actions verified; step/spend/loop guards enforced; tool allowlist per tenant; full action audit log; trajectory eval gate in CI; run timeouts + resumable checkpoints; concurrency quotas per tenant.

**15. Transformation roadmap.**
1. Config/secrets cleanup + dependency pinning.
2. Restructure into `agents/tools/runs/memory` modules.
3. Define tools with strict schemas + arg validation (no free-form exec).
4. Convert agent to **LangGraph** with explicit state + checkpointing.
5. Add **step/loop/spend guards** (highest-risk-first).
6. Persist run/step state to Postgres; expose run-status API.
7. Move execution to background workers + SSE progress streaming.
8. Add Langfuse tracing per step (tool, latency, cost).
9. Add human-in-loop interrupt + approval API/UI for destructive actions.
10. Scope per-tool least-privilege credentials + tool allowlist.
11. Add prompt-injection/tool-hijack defenses + output filtering.
12. Build trajectory golden tasks + eval runner; wire CI gate.
13. Add per-run/tenant cost budgets + kill-switch.
14. Containerize; docker-compose; Trivy scan.
15. Terraform + EKS deploy; HPA on queue depth; PDB/probes.
16. OTel + Langfuse dashboards + alerts; audit-log retention.
17. k6 concurrent-run load test; tune worker autoscaling.
18. Runbook (incl. "agent did something wrong" recovery), README, diagram.

---

## PACKAGE 3 — Production-grade fine-tuned LLM application

**1. Definition and use cases.** Domain-tuned model served behind the full stack. Use cases: brand-voice generator; clinical-note structured extractor; internal-SDK code assistant.

**2. Frontend layer.** Same base as P1. Often simpler UI (single-purpose generate/extract) but keep streaming + retry + cancel.

**3. Backend layer.** FastAPI inference gateway in front of the model server: request validation, batching hints, timeout/retry, fallback to a base/hosted model if the fine-tuned endpoint is down. REST (+ SSE for generation).

**4. AI/ML core (this package's center of gravity).**
- **Data prep pipeline** (the real bottleneck): collection → dedup → clean → PII-scrub → format to instruction/chat schema → train/val/test split → quality review. Versioned datasets (DVC / S3 + manifest).
- **Method selection:** **QLoRA** default (cost-effective, your strength); LoRA when you have more VRAM/quality need; **full fine-tune** only with strong justification + budget; **DPO/preference tuning** when you have preference pairs and quality plateaus; instruction-tuning for format adherence. RLHF generally out of scope (cost/complexity).
- **Base model:** Llama-3.x / Qwen-2.5 / Mistral by license + size + benchmark fit.
- **Training infra:** SageMaker training jobs (your experience) or a rented GPU (Lambda/RunPod) for cost; track with **MLflow / Weights & Biases**.
- **Serving:** **vLLM** (default — throughput, continuous batching, LoRA hot-swap) on a GPU node; alt **TGI**; **SageMaker endpoint** if client is SageMaker-centric; **Bedrock custom model import** for managed. Model registry + versioned adapters.

**5. Data layer.** Postgres (requests, feedback, eval results). S3 (datasets, checkpoints, adapters — versioned). Redis (response cache). Optional vector DB only if combined with RAG. **Model registry** (MLflow/SageMaker) is the key addition.

**6. Infrastructure.** GPU is the differentiator. EKS with **GPU node pool** (autoscale 0→N; cold-start matters), or SageMaker endpoints with autoscaling. Docker: CUDA base image, weights/adapters pulled from S3 at startup (not baked), layer-cache deps. Terraform manages GPU node groups, ECR, model bucket, endpoints. Spot GPUs for training; on-demand/reserved for serving.

**7. CI/CD.** Two pipelines: **code CD** (gateway/app) and **model CD** (data → train → eval → register → canary deploy). Model promotion gated on eval metrics vs current prod model; rollback = repoint endpoint to previous adapter version. Version data + model + code together.

**8. Observability.** App via OTel. **Model-specific:** inference latency (p50/p95/p99), tokens/sec, GPU utilization/memory, batch efficiency, **quality drift** (online eval sampling vs golden set), fallback-rate to base model. Langfuse for prompt/response traces + cost (compute cost here, not token API cost).

**9. Security and compliance.** Training data is the risk: **PII scrubbing before training** (models memorize); dataset access control + lineage; protect adapters/weights (IP); output filtering; for regulated data, self-host end-to-end (no data leaves VPC) — a key selling point of fine-tuning. Audit dataset provenance.

**10. Scaling for millions of users.** Continuous batching (vLLM) is the main lever; GPU autoscaling on queue depth + latency; multi-replica + load balancing; **multi-LoRA serving** (one base, many adapters) to serve many tenants cheaply; response cache; quantization (AWQ/GPTQ) for throughput.
- **Bottleneck checklist:** (1) GPU cost/availability → quantize, batch, autoscale-to-zero off-peak; (2) cold-start on scale-up → warm pool / min replicas; (3) throughput ceiling → vLLM continuous batching + more replicas; (4) quality drift → online eval + retrain trigger; (5) single big model for all tenants → multi-LoRA.

**11. Cost controls.** Spot for training; quantization + batching for serving; autoscale-to-zero off-peak; cache; route simple requests to base/cheap model, fine-tuned only where it adds value; GPU-spend alerts + budget caps.

**12. Testing and eval.** Unit (data-prep transforms, gateway). **Model eval is central:** held-out test set + task metrics (accuracy/F1/BLEU/ROUGE or LLM-judge), regression vs current prod model as a **promotion gate**, online eval sampling, A/B fine-tuned-vs-base. Load/throughput test on the GPU endpoint (tokens/sec at concurrency).

**13. Reference project structure.**
```
ft-llm-app/
├── frontend/
├── backend/             # FastAPI inference gateway + fallback
├── training/
│   ├── data_pipeline/   # collect, clean, pii_scrub, format, split
│   ├── train/           # qlora config, train script, hp
│   ├── eval/            # test set, metrics, promotion gate
│   └── serving/         # vllm config, model loader
├── infra/terraform/     # gpu node group, ecr, model bucket, endpoint
├── models/              # registry pointers, adapter versions (S3-backed)
├── .github/workflows/   # code-cd.yml, model-cd.yml
└── docker-compose.yml
```

**14. Production hardening checklist.** PII scrubbed + dataset lineage tracked; data/model/code versioned together; eval-gated model promotion + rollback; GPU autoscaling + warm pool; quantized serving; base-model fallback verified; weights/adapters access-controlled; GPU cost alerts + caps; throughput load-tested; quality-drift monitoring + retrain trigger; runbook for bad-model rollback.

**15. Transformation roadmap.**
1. Config/secrets cleanup; dependency + CUDA base pinning.
2. Build versioned **data-prep pipeline** (clean, PII-scrub, format, split) — biggest risk first.
3. Add held-out eval set + metric script.
4. Reproducible **QLoRA training script** + experiment tracking (MLflow/W&B).
5. Build inference gateway (FastAPI) with validation + base-model fallback.
6. Stand up **vLLM serving** with the adapter; measure tokens/sec.
7. Add model registry + versioned adapters in S3.
8. Add Langfuse + model metrics (latency, GPU, drift).
9. Build eval-gated **model-CD** pipeline (train→eval→register→canary).
10. Add response cache + request routing (base vs fine-tuned).
11. Quantize + tune continuous batching for throughput.
12. Containerize (CUDA, weights-from-S3); Trivy scan.
13. Terraform GPU node group + ECR + endpoint + autoscaling.
14. Deploy to EKS GPU pool (or SageMaker); warm pool + HPA on queue.
15. GPU cost alerts + budget caps + autoscale-to-zero off-peak.
16. Throughput load test; tune batching/replicas.
17. Quality-drift monitor + retrain trigger; runbook + diagram.

---

## PACKAGE 4 — Document Intelligence pipeline

**1. Definition and use cases.** High-throughput parse→extract→structure→index pipeline. Use cases: invoice/PO extraction to ERP; contract clause extraction + risk flags; resume parsing + ranking.

**2. Frontend layer.** Often a **review/correction dashboard** (Next.js): upload, see extracted fields with confidence, human-correct low-confidence, export. Bulk-upload + job-status views. Streaming less relevant; **progress + batch status** matters.

**3. Backend layer.** FastAPI control plane + **worker fleet** for processing. Heavy use of **background jobs/queues** (this is a batch/throughput system, not request/response). Idempotent per-document processing; dead-letter queue for failures. REST + webhooks for completion.

**4. AI/ML core.**
- Parsing: **layout-aware extraction** — default **AWS Textract** (tables/forms) or **unstructured.io**; alt **LlamaParse** / **Docling**; OCR via Textract/Tesseract for scans. Vision-LLM (GPT-4o / Claude) for complex/low-structure docs.
- Extraction: **LLM structured output** (function calling / JSON schema, Pydantic-validated) with confidence scoring; few-shot per doc type. Orchestration: **LlamaIndex** (default — strongest doc/ingestion tooling) or **custom pipeline**; LangGraph if routing by doc type with branches.
- If feeding RAG: chunk + embed + index as the pipeline's output stage.

**5. Data layer.** Postgres (documents, extracted records, job state, corrections — the system of record). S3 (raw + processed docs). Queue: **SQS / Celery** (core component). Redis (job status, dedup). Vector DB only if output feeds RAG. Search index (OpenSearch) if users browse extracted data.

**6. Infrastructure.** AWS-native fits best here: **S3 + SQS + Lambda/Fargate workers + Textract + Step Functions** for the pipeline (Step Functions is genuinely better than K8s for multi-stage doc workflows). Alt: EKS workers if you want portability. Terraform for the whole pipeline. **This is the one package where AWS managed services > K8s.**

**7. CI/CD.** GitHub Actions: test parsers/extractors on a fixture doc set; **extraction-accuracy eval gate**; deploy workers + Step Functions. Version extraction prompts/schemas per doc type.

**8. Observability.** Throughput (docs/min), per-stage latency, **extraction accuracy + confidence distribution**, human-correction rate, failure/DLQ rate, cost per document. OTel + CloudWatch; Langfuse for the LLM extraction steps.

**9. Security and compliance.** Documents are often sensitive (invoices, contracts, PII-heavy). Encrypt at rest (S3+KMS) + in transit; PII detection/redaction; per-document access control; audit every access + extraction; data residency (keep in-region); retention/deletion policy. For regulated clients, keep everything in-VPC (Textract + Bedrock).

**10. Scaling for millions of users (documents).** Horizontal worker scaling on **queue depth**; batch where possible; parallelize per-page; cache results for duplicate docs; backpressure + DLQ; partition by tenant. CDN not relevant; throughput is the game.
- **Bottleneck checklist:** (1) parser/OCR throughput → parallelize, autoscale workers; (2) LLM extraction cost/rate → batch, cheaper model for simple docs, cache; (3) large files → stream/chunk, per-page processing; (4) failures silently lost → DLQ + retries + alerting; (5) DB write contention at scale → batch writes, partition.

**11. Cost controls.** Cheap model for simple docs, escalate for complex; OCR-cache duplicates; batch LLM calls; per-tenant doc quotas; cost-per-document dashboard + alerts.

**12. Testing and eval.** Unit (parsers, schema validation). **Extraction-accuracy eval** against a labeled fixture set (field-level precision/recall) as CI gate; regression on new prompt/model versions. Load test the pipeline at target docs/min.

**13. Reference project structure.**
```
doc-intel/
├── frontend/            # review/correction dashboard
├── backend/             # control plane API + webhooks
├── pipeline/
│   ├── ingest/          # upload, dedup, queue
│   ├── parse/           # textract/unstructured adapters, OCR
│   ├── extract/         # llm structured extraction per doc type
│   ├── postprocess/     # validate, confidence, persist
│   └── index/           # optional embed+index for RAG
├── infra/terraform/     # s3, sqs, step functions, fargate, textract
├── eval/                # labeled fixtures, accuracy runner
└── .github/workflows/
```

**14. Production hardening checklist.** Encryption + KMS; PII redaction; per-doc access control + audit; DLQ + retries + alerting; idempotent processing; extraction-accuracy eval gate; confidence-thresholded human review; throughput load-tested; cost-per-doc tracked; retention/deletion policy; in-region/in-VPC for regulated data.

**15. Transformation roadmap.**
1. Config/secrets cleanup; dependency pinning.
2. Restructure into `ingest/parse/extract/postprocess` stages.
3. Define per-doc-type **Pydantic extraction schemas** + validation.
4. Add layout-aware parser (Textract/unstructured) behind an adapter.
5. LLM structured extraction with confidence scoring.
6. Persist documents + records + job state to Postgres; S3 for files.
7. Move to **queue-driven workers** (SQS/Celery) + idempotency + DLQ.
8. Build labeled fixture set + accuracy eval; wire CI gate.
9. Add review/correction dashboard for low-confidence fields.
10. Add Langfuse + throughput/accuracy/cost observability.
11. Encryption + PII redaction + access control + audit log.
12. Cost routing (cheap vs strong model) + dedup cache + quotas.
13. Containerize workers; Terraform S3+SQS+Step Functions+Fargate.
14. Deploy; autoscale workers on queue depth.
15. Load test at target docs/min; tune; runbook + diagram.

---

## PACKAGE 5 — AI microservice into an existing system

**1. Definition and use cases.** A self-contained GenAI capability dropped into a client's existing app via API — lowest-risk entry point. Use cases: summarize/smart-reply for a support tool; semantic search for a catalog; auto-tagging behind a CMS.

**2. Frontend layer.** Usually **none of your own** — you expose an API the client's frontend calls. Optionally a small embeddable widget (web component / iframe) or a demo/admin UI. If embeddable: framework-agnostic web component + streaming via SSE.

**3. Backend layer (the whole package).** FastAPI service with a **clean, versioned, well-documented API** (OpenAPI spec is a deliverable). API-key/JWT auth for service-to-service. Idempotency, rate limiting, timeouts, graceful fallback. Must be **drop-in**: minimal assumptions about the host system, clear contract. REST default; gRPC if the client's stack is gRPC; webhooks for async results.

**4. AI/ML core.** Whatever the capability needs (RAG-lite, classification, summarization, embeddings) — but **scoped tight**. Tiered models for cost. Orchestration: keep it **thin/custom** unless the task genuinely needs LangGraph — a microservice should be lightweight. Prompt versioning via Langfuse.

**5. Data layer.** Minimal by design — ideally **stateless** or thin Postgres for its own data; Redis for cache/rate-limit. Vector DB only if the capability is semantic search/RAG. Avoid coupling to the client's DB; integrate via API/events.

**6. Infrastructure.** **ECS Fargate or Cloud Run** (default — simpler than K8s for a single service; this is the package where full EKS is usually overkill). EKS only if the client already runs K8s and wants it deployed there. Docker single-image; Terraform minimal (service + ALB + secrets + cache). Provider-API inference (self-hosting rarely justified for one microservice).

**7. CI/CD.** GitHub Actions: test → build → deploy. **API contract tests** (schema/compat) are key — you must not break the client's integration. Semantic versioning of the API; deprecation policy.

**8. Observability.** Per-endpoint latency/error rate (you'll be held to an SLA), token/cost, usage per API key. OTel + Langfuse. Expose a status/health endpoint the client can monitor. Clear error contracts.

**9. Security and compliance.** Service-to-service auth (API keys/mTLS/JWT); strict input validation (you're an attack surface in someone else's system); rate limiting per key; output filtering; **don't log client payloads** unless contracted (PII liability); secrets in Secrets Manager; clear data-handling agreement.

**10. Scaling for millions of users.** Stateless + horizontal scale behind ALB; aggressive caching (semantic/response); model tiering; per-key quotas to prevent one client overloading you; regional deployment if the host is multi-region.
- **Bottleneck checklist:** (1) one client's traffic starves others → per-key rate limits/quotas (do first); (2) LLM cost/latency → cache + tiering; (3) cold starts (Fargate/Cloud Run) → min instances; (4) breaking API changes → versioning + contract tests; (5) downstream provider outage → fallback + circuit breaker.

**11. Cost controls.** Per-key token budgets + quotas; cheap-model default; response/semantic cache; usage-based internal cost attribution per client; spend alerts + per-key kill-switch.

**12. Testing and eval.** Unit + integration; **API contract/compat tests**; capability-specific LLM eval (e.g., summarization quality) in CI; load test per-endpoint to SLA; backward-compat regression.

**13. Reference project structure.**
```
ai-microservice/
├── app/
│   ├── api/v1/          # versioned endpoints + openapi
│   ├── core/            # config, auth, rate_limit, cache
│   ├── capability/      # the actual AI logic (thin)
│   └── observability/
├── tests/{unit,integration,contract,eval}/
├── infra/terraform/     # fargate/cloud-run, alb, secrets, redis
├── .github/workflows/
└── Dockerfile
```

**14. Production hardening checklist.** Versioned API + contract tests + deprecation policy; service auth + per-key rate limits/quotas; strict input validation + output filtering; no PII logging (or contracted); SLA-backed latency/error monitoring + alerting; cache live; cost per-key + kill-switch; circuit breaker on provider; min-instances for cold start; clear error contract + status endpoint; integration/runbook doc for the client.

**15. Transformation roadmap.**
1. Define the **API contract** (OpenAPI) + versioning scheme first.
2. Config/secrets cleanup; thin, stateless structure.
3. Implement the capability behind the versioned endpoint + Pydantic I/O.
4. Add service auth (API keys/JWT) + strict input validation.
5. Add per-key rate limiting + quotas.
6. Add Redis cache (response/semantic) + model tiering.
7. Add Langfuse + per-endpoint/per-key latency/cost/error metrics.
8. Add capability eval + **contract/compat tests** in CI.
9. Add circuit breaker + provider fallback + clear error contract.
10. Containerize; Terraform Fargate/Cloud Run + ALB + secrets + Redis.
11. Deploy; min-instances; autoscale on RPS.
12. Cost per-key + kill-switch + alerts.
13. Load test to SLA; tune.
14. Write client integration guide + runbook + status endpoint.

---

## PACKAGE 6 — Multi-modal AI application (vision + voice + text)

**1. Definition and use cases.** App combining image/audio with text. Use cases: voice assistant (Whisper→reason→TTS); visual QA (photo→identify+answer); image triage + text report.

**2. Frontend layer.** Next.js. Divergence: **media capture/upload UX** — mic recording + waveform, camera/file upload, audio playback for TTS, image preview with annotations. Stream partial transcripts (live STT) and stream TTS audio chunks; cancel/retry on long media ops.

**3. Backend layer.** FastAPI. Divergence: **large binary handling** — presigned S3 upload (don't proxy big files through the API), async media-processing jobs, streaming audio in/out, chunked transfer. Background workers for transcription/vision. REST + SSE/websocket for streaming media.

**4. AI/ML core.**
- Speech-to-text: **Whisper** (your experience) — `whisper.cpp`/faster-whisper self-host or OpenAI/Deepgram API. Text-to-speech: ElevenLabs (quality default) / OpenAI TTS / Coqui (self-host). Vision: **GPT-4o / Claude vision** (default for VQA) or self-host ViT/CLIP/segmentation models (your fine-tuning experience) for specialized classification.
- Orchestration: pipeline/LangGraph routing across modalities (transcribe → reason → synthesize). Combine with RAG for grounded answers. Prompt + model versioning per modality.

**5. Data layer.** S3 (audio/image/video — central). Postgres (sessions, transcripts, results). Redis (cache, job status). Vector DB if RAG-grounded or image-embedding search. Possibly a CDN for serving generated media.

**6. Infrastructure.** EKS with **GPU pool** if self-hosting Whisper/vision/TTS; otherwise provider APIs + Fargate. Docker with CUDA + model weights from S3 for self-hosted media models. Terraform for GPU nodes + S3 + CDN (CloudFront for media). Inference: Whisper/ViT on vLLM/Triton or managed APIs; pick managed first, self-host when volume/cost/privacy demands.

**7. CI/CD.** GitHub Actions: test each modality stage; eval gate on transcription WER / vision accuracy / output quality; deploy. Version models per modality.

**8. Observability.** Per-modality latency (STT, vision, LLM, TTS), end-to-end latency (critical for voice UX), accuracy (WER, vision metrics), GPU utilization if self-hosted, cost per interaction (media is expensive). OTel + Langfuse.

**9. Security and compliance.** Media is sensitive (voices, faces, documents-as-images) — biometric/PII implications. Encrypt media at rest/transit; access control + signed URLs; consent/retention for voice/face data (legal exposure); content moderation on generated media; PII in transcripts redacted; audit access.

**10. Scaling for millions of users.** Presigned uploads (offload from API); async job queues for heavy media; GPU autoscaling on queue depth; cache transcriptions/vision results; CDN for media delivery; tier (cheap model for simple, escalate); regional processing for latency.
- **Bottleneck checklist:** (1) big-file upload through API → presigned S3 direct (do first); (2) GPU media-model throughput → batch, autoscale, managed API fallback; (3) end-to-end voice latency → streaming STT/TTS + co-located services; (4) media storage/egress cost → lifecycle policies + CDN; (5) job backlog → queue autoscale + backpressure.

**11. Cost controls.** Media inference is pricey: cache aggressively; cheap model default; managed API vs self-host cost analysis per volume; per-user media quotas; S3 lifecycle (expire raw media); cost-per-interaction alerts.

**12. Testing and eval.** Unit per stage; integration across modalities; eval: **WER for STT**, accuracy for vision, quality/MOS-style for TTS, end-to-end task success; load test media throughput.

**13. Reference project structure.**
```
multimodal-app/
├── frontend/            # capture/upload, playback, streaming
├── backend/             # api + presigned uploads + sse/ws
├── modalities/
│   ├── stt/ vision/ tts/ # adapters (managed + self-host)
│   └── orchestrator/     # cross-modal pipeline
├── workers/             # async media processing
├── infra/terraform/     # gpu pool, s3, cloudfront
├── eval/                # wer, vision, tts eval sets
└── .github/workflows/
```

**14. Production hardening checklist.** Presigned uploads; media encryption + signed URLs + access control; consent/retention for biometric data; content moderation on outputs; transcript PII redaction; per-modality + e2e latency monitoring; GPU autoscaling; cache; media cost controls + S3 lifecycle; eval gates (WER/vision/quality); CDN; runbook.

**15. Transformation roadmap.**
1. Config/secrets cleanup; structure into `modalities/` adapters.
2. Move uploads to **presigned S3** (offload API) — first.
3. Wrap each modality (STT/vision/TTS) behind adapters (managed default).
4. Build cross-modal orchestrator (transcribe→reason→synthesize).
5. Async workers for heavy media + job-status API.
6. Streaming STT in / TTS out + cancel/retry in UI.
7. Add Langfuse + per-modality + e2e latency/cost metrics.
8. Eval sets (WER, vision accuracy, TTS quality); CI gate.
9. Media encryption, signed URLs, access control, consent/retention.
10. Content moderation + transcript PII redaction.
11. Cache + model tiering + per-user media quotas + S3 lifecycle.
12. Containerize (CUDA if self-hosting); Terraform GPU+S3+CloudFront.
13. Deploy; GPU autoscale on queue depth; CDN for media.
14. Cost alerts; load test media throughput; runbook + diagram.

---

## PACKAGE 7 — LLM Evaluation & Observability platform

**1. Definition and use cases.** Instrumentation + eval harness + dashboards that make *someone else's* LLM app measurable, testable, cost-controlled. Use cases: drop-in eval+tracing for a hallucinating RAG bot; regression-gating CI for blind prompt changes; cost/latency dashboard + kill-switches.

**2. Frontend layer.** A **dashboard** (Next.js): traces explorer, eval-result trends, cost/latency charts, A/B comparisons, alert config. Read-heavy; tables, charts (Recharts/Tremor), filtering. Often you deploy/customize **Langfuse's own UI** rather than build from scratch — decide build-vs-adopt early.

**3. Backend layer.** FastAPI ingestion API (receive traces/spans from the client's app via SDK/proxy) + query API for the dashboard. **High write throughput** (every LLM call emits spans) → async ingestion + batching + a time-series/columnar store. REST + an SDK/proxy the client embeds.

**4. AI/ML core.** The "AI" here is **eval methodology**, not an app: LLM-as-judge graders, RAGAS/DeepEval metric implementations, embedding-based similarity for regression, drift detection. Default: **adopt Langfuse (self-hosted) + RAGAS/promptfoo** and build the client-specific eval logic + dashboards on top, rather than reinventing tracing. Build custom only when the client needs something Langfuse can't express.

**5. Data layer.** **ClickHouse / Postgres+Timescale** for trace/metric storage (high-volume time-series — this is the core choice; Langfuse uses ClickHouse). Postgres for config/eval-sets. Redis (cache, rate limit). S3 (raw trace archive). This package is **data-store-defined**.

**6. Infrastructure.** EKS or ECS; Langfuse via Helm/compose if adopting. Terraform for the store (ClickHouse/RDS) + app + ingestion. Scaling concern is **ingestion write volume**, not GPU. No inference hosting unless running judge models self-hosted.

**7. CI/CD.** GitHub Actions. The product *is* CI integration — ship a reusable **eval-gate action/CLI** clients drop into their pipeline. Version eval sets + grader prompts.

**8. Observability.** Meta: the platform must be observable itself (ingestion lag, dropped spans, store latency). Tracks for clients: token/cost, latency breakdown, eval scores over time, hallucination/groundedness rate, regression flags, A/B results.

**9. Security and compliance.** You're ingesting the client's prompts/responses = **potentially their most sensitive data**. PII redaction at ingestion; tenant isolation (hard requirement — multi-tenant by nature); encryption; access control; data residency; retention controls; don't leak one client's data to another. This is the package where multi-tenancy security is non-negotiable.

**10. Scaling for millions of users (events).** Ingestion is the scale problem: batch + async + queue in front of the store; columnar store (ClickHouse) for query at volume; sampling for very high-volume clients; partition by tenant; downsample/rollup old data.
- **Bottleneck checklist:** (1) ingestion write throughput → queue + batch + ClickHouse (first); (2) dashboard query latency on big ranges → rollups/materialized views; (3) judge-LLM eval cost at volume → sample, cheap judge model; (4) storage growth → retention + downsampling; (5) tenant data isolation under load → partition + row-level security.

**11. Cost controls.** Sampling for high-volume traces; cheap judge models; rollups to cut storage; per-tenant ingestion quotas; the platform itself sells cost control to clients (eat your own dog food).

**12. Testing and eval.** Unit (graders, metric math, ingestion); integration (SDK→ingest→query); **meta-eval** (do the graders agree with human labels?); load test ingestion at high event rate.

**13. Reference project structure.**
```
llm-eval-obs/
├── frontend/            # dashboard (or customized Langfuse UI)
├── ingestion/           # high-throughput span/trace API + batching
├── query/               # dashboard query API
├── eval/
│   ├── graders/         # llm-judge, ragas, deepeval wrappers
│   ├── datasets/        # golden/eval sets per client
│   └── ci/              # reusable eval-gate cli/action
├── sdk/                 # client SDK/proxy to emit traces
├── infra/terraform/     # clickhouse/timescale, app, queue
└── .github/workflows/
```

**14. Production hardening checklist.** Multi-tenant isolation verified; PII redaction at ingestion; encryption + access control + residency + retention; ingestion lag/drop monitoring; queue + batching under load; rollups for query perf; meta-eval of graders vs human labels; reusable CI eval-gate shipped; per-tenant quotas; sampling for high-volume; backup of trace store.

**15. Transformation roadmap.**
1. Decide **adopt Langfuse vs build** (default: adopt + extend); cleanup config/secrets.
2. Stand up trace store (ClickHouse/Timescale) + ingestion API with batching.
3. Build client **SDK/proxy** to emit spans from their app.
4. Implement **graders** (LLM-judge, RAGAS, DeepEval) + golden-set loader.
5. Add **meta-eval** (graders vs human labels) to trust the metrics.
6. Build dashboard (traces, cost, latency, eval trends, A/B).
7. Ship a reusable **CI eval-gate** CLI/action for regression gating.
8. Add cost/latency/groundedness alerting + kill-switch hooks.
9. **Multi-tenant isolation** + PII redaction + access control (non-negotiable).
10. Add sampling + per-tenant quotas + rollups for scale.
11. Containerize; Terraform store + app + queue.
12. Deploy; load test ingestion at high event rate; tune.
13. Retention/downsampling + backup; runbook + client onboarding doc.

---

## Cross-package notes

- **Shared platform substrate** across all seven: Postgres, Redis, S3, FastAPI, Next.js, Docker, Terraform, GitHub Actions, OTel+Grafana, Langfuse, Cognito/Clerk auth, AWS Secrets Manager+KMS, k6. Build this substrate once (templates/modules) and each package becomes a specialization on top — this is how you deliver 7 packages without 7× the work.
- **Build packages in this order for skill-compounding:** 1 (RAG) → 5 (microservice, reuses RAG, low risk) → 4 (doc-intel, reuses ingestion) → 2 (agentic, hardest, builds on RAG) → 7 (eval/obs, sells your own gap-closing) → 3 (fine-tune, GPU/cost) → 6 (multi-modal, GPU/media). Each reuses the prior substrate and closes more of the gap list.
- **The differentiator in every package is layers 8–12** (observability, security, scaling, cost, eval). Anyone can build the happy path with Claude Code; these layers are what make it "production-grade" and what justify the rates in `02-market-positioning.md`.
