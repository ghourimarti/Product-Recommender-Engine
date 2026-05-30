# Phase 1 — Requirements & Non-Functional Targets

> Status: **DRAFT / awaiting sign-off.** Target project: P2 Product Recommender. Package: Production-grade RAG. All numbers marked `[PROPOSED]` until confirmed.

## Functional Scope (what it must do)
1. Conversational product Q&A / recommendation over product catalog + reviews, multi-turn.
2. **Per-user, isolated session history** (fixes the current shared `"user-session"` bug — all users currently share one memory).
3. Retrieval with **citations** (which products/reviews grounded the answer).
4. A clean **JSON API** (not form-POST) with **token streaming** to the UI.
5. **Recommendation/semantic-search endpoint** ("show me products like X / for use-case Y").
6. **Catalog ingestion/refresh** path (re-index when products/reviews change) without downtime.
7. Admin/health/metrics endpoints.

## Non-Functional Requirements `[PROPOSED]`

| Dimension | Target | Note |
|---|---|---|
| Latency — first token (p50/p95/p99) | 0.8s / 2.0s / 4.0s | Streamed; Groq llama-3.1-8b is fast, so this is realistic |
| Latency — full answer (p95) | ≤ 6s | Streamed end-to-end |
| Latency — recommend/search (p95) | ≤ 400ms | Vector search only, no generation |
| Throughput | 100 RPS sustained, **300 RPS peak** | Drives HPA + connection pooling targets |
| Scale model | **1M MAU, 50k DAU, peak 500 concurrent** | The "millions of users" target we design + load-test against |
| Uptime SLO | **99.9%** (~43 min/mo error budget) | 99.95% is achievable but costs more; 99.9% is the honest tier |
| Cost ceiling — per request | ≤ **$0.004** (blended w/ cache) | Cache + cheap-default model are the levers |
| Cost ceiling — monthly infra+LLM | ≤ **$2,500/mo** at the scale above | Realistic for this tier; load test validates |
| Compliance | **GDPR-aware**, no HIPAA/PCI, SOC2 *aware* not certified | User accounts + chat history = personal data |
| Data residency | Single region (**us-east-1**) default; EU note | Multi-region is out-of-scope v1 |

## Out of Scope (explicitly NOT building)
- Payment/checkout, real order placement, inventory writes — recommend only.
- The storefront itself (we expose API + a reference chat UI, not a full e-commerce site).
- Native mobile apps.
- Multi-language / i18n (English v1).
- Custom model **fine-tuning** (this is the RAG package; tiering uses hosted models).
- Human-agent handoff / live chat.
- Multi-region active-active and SOC2/HIPAA certification.

## Open inputs I need from you (drive later phases; defaults assumed if silent)
- **Real budget for cloud during the build** (governs whether we load-test on real EKS vs simulate). Default assumption: small, so we design for scale but validate with bounded load tests.
- **Catalog size at target** (current demo = 450 reviews). Default assumption: design for ~1–5M review/product vectors.
- **Auth required for v1?** Default assumption: yes, lightweight (needed for per-user history + rate limiting + GDPR).
