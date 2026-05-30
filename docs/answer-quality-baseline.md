# Answer-Quality Baseline (Step 7)

> Custom LLM-judge harness (RAGAS-style metrics). Answers from the real pipeline (Groq primary); judged by OpenAI gpt-4o. Contexts = product evidence texts.

## Aggregate (mean over queries)

| metric | mean |
|---|---|
| faithfulness | 0.5625 |
| answer_relevancy | 0.9375 |
| context_precision | 0.675 |

## Per-query

| query | faithfulness | answer_relevancy | context_precision |
|---|---|---|---|
| headphones with the best bass | 0.50 | 1.00 | 0.67 |
| wireless earbuds with long battery life | 1.00 | 1.00 | 0.90 |
| earphones that are good for taking calls | 0.50 | 1.00 | 0.67 |
| budget bluetooth headphones under a tigh | 0.50 | 1.00 | 0.67 |
| boat headphones for listening to music | 0.50 | 1.00 | 0.50 |
| wired earphones with good sound quality | 0.50 | 1.00 | 0.67 |
| a bluetooth neckband for workouts at the | 0.50 | 1.00 | 0.67 |
| earbuds for gaming with low latency | 0.50 | 0.50 | 0.67 |

## Methodology & honest caveats

- **Not the RAGAS library** — every ragas release hard-imports a removed `langchain_community.chat_models.vertexai`, incompatible with our langchain-core>=0.3 stack. This custom harness implements the same metric definitions via an LLM judge.
- **Judge = OpenAI gpt-4o** (Anthropic key unavailable; Decision 19 wanted an off-family judge). OpenAI is a *fallback* answer provider, but the **primary** answer model is Groq, so the judge is off the primary.
- 8 queries on a 9-product catalog: a sanity check, not a benchmark.

## CI regression gate (from this baseline)

- Gate: **faithfulness ≥ 0.5625 − 0.05** and **answer_relevancy ≥ 0.9375 − 0.05**.
- Re-baseline whenever prompts, the answer model, or retrieval change.
