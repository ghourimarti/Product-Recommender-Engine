"""Answer-quality runner (Step 7): faithfulness / answer-relevancy / context-precision.

    uv run python -m evaluation.ragas.run      # needs Qdrant up + OPENAI_API_KEY (judge)

Decision 19 named RAGAS, but every ragas release hard-imports
``langchain_community.chat_models.vertexai`` (removed for langchain-core>=0.3, which our
LLM stack requires) -> unresolvable dependency conflict. This is an equivalent custom
LLM-judge harness using the same metric definitions: answers come from the real pipeline
(Groq primary), judged by OpenAI gpt-4o. Writes docs/answer-quality-baseline.md.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr

from core.config import get_settings
from core.llm import build_chat_model, explain
from core.models import ExplanationSet
from recommender.service import recommend
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

GOLDEN_PATH = Path(__file__).parent / "golden_set.json"
REPORT_OUT = Path("docs/answer-quality-baseline.md")
K = 3
METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision")

JUDGE_SYSTEM = (
    "You are a strict evaluator of a product-recommendation answer. Score each metric in "
    "[0,1]:\n"
    "- faithfulness: is EVERY claim in the answer supported by the provided review contexts? "
    "Penalize unsupported or invented claims.\n"
    "- answer_relevancy: does the answer directly address the shopper's query?\n"
    "- context_precision: what fraction of the provided contexts are relevant to the query?\n"
    "Be critical and consistent."
)
JUDGE_HUMAN = "Query: {query}\n\nAnswer:\n{answer}\n\nContexts:\n{contexts}"


class RagasQuery(BaseModel):
    query: str


class JudgeScores(BaseModel):
    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    context_precision: float = Field(ge=0.0, le=1.0)


def load_golden(path: Path = GOLDEN_PATH) -> list[RagasQuery]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [RagasQuery.model_validate(item) for item in raw]


def format_answer(expl: ExplanationSet) -> str:
    """Flatten the structured explanation into the answer text the judge evaluates."""
    reasons = "\n".join(f"{e.product_id}: {e.reason}" for e in expl.explanations)
    return f"{expl.summary}\n{reasons}".strip()


def _answer_and_contexts(query: str, store: QdrantHybridStore, model: Any) -> tuple[str, list[str]]:
    result = recommend(query, store, k=K)
    contexts = [p.text for p in result.products]
    if not result.products:
        return "No good match found.", contexts
    return format_answer(explain(query, result.products, model)), contexts


def judge_sample(query: str, answer: str, contexts: list[str], judge_model: Any) -> JudgeScores:
    structured = judge_model.with_structured_output(JudgeScores)
    prompt = ChatPromptTemplate.from_messages([("system", JUDGE_SYSTEM), ("human", JUDGE_HUMAN)])
    chain = prompt | structured
    result: JudgeScores = chain.invoke(
        {"query": query, "answer": answer, "contexts": "\n---\n".join(contexts)}
    )
    return result


def _means(rows: list[tuple[str, JudgeScores]]) -> dict[str, float]:
    return {
        name: (round(statistics.fmean(getattr(s, name) for _, s in rows), 4) if rows else 0.0)
        for name in METRIC_NAMES
    }


def build_report(rows: list[tuple[str, JudgeScores]]) -> str:
    means = _means(rows)
    lines: list[str] = [
        "# Answer-Quality Baseline (Step 7)",
        "",
        "> Custom LLM-judge harness (RAGAS-style metrics). Answers from the real pipeline "
        "(Groq primary); judged by OpenAI gpt-4o. Contexts = product evidence texts.",
        "",
        "## Aggregate (mean over queries)",
        "",
        "| metric | mean |",
        "|---|---|",
    ]
    lines += [f"| {name} | {means[name]} |" for name in METRIC_NAMES]
    lines += [
        "",
        "## Per-query",
        "",
        "| query | faithfulness | answer_relevancy | context_precision |",
        "|---|---|---|---|",
    ]
    for query, scores in rows:
        lines.append(
            f"| {query[:40]} | {scores.faithfulness:.2f} | "
            f"{scores.answer_relevancy:.2f} | {scores.context_precision:.2f} |"
        )
    lines += [
        "",
        "## Methodology & honest caveats",
        "",
        "- **Not the RAGAS library** — every ragas release hard-imports a removed "
        "`langchain_community.chat_models.vertexai`, incompatible with our langchain-core>=0.3 "
        "stack. This custom harness implements the same metric definitions via an LLM judge.",
        "- **Judge = OpenAI gpt-4o** (Anthropic key unavailable; Decision 19 wanted an "
        "off-family judge). OpenAI is a *fallback* answer provider, but the **primary** answer "
        "model is Groq, so the judge is off the primary.",
        "- 8 queries on a 9-product catalog: a sanity check, not a benchmark.",
        "",
        "## CI regression gate (from this baseline)",
        "",
        f"- Gate: **faithfulness ≥ {means['faithfulness']} − 0.05** and "
        f"**answer_relevancy ≥ {means['answer_relevancy']} − 0.05**.",
        "- Re-baseline whenever prompts, the answer model, or retrieval change.",
    ]
    return "\n".join(lines) + "\n"


def run() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        sys.exit("OPENAI_API_KEY required for the LLM judge.")

    store = QdrantHybridStore()
    store.index(load_catalog())
    answer_model = build_chat_model()
    judge_model = ChatOpenAI(
        model=settings.openai_model,
        api_key=SecretStr(settings.openai_api_key),
        temperature=0,
    )

    rows: list[tuple[str, JudgeScores]] = []
    for item in load_golden():
        answer, contexts = _answer_and_contexts(item.query, store, answer_model)
        rows.append((item.query, judge_sample(item.query, answer, contexts, judge_model)))

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(build_report(rows), encoding="utf-8")

    print("answer-quality means:", _means(rows))
    print(f"wrote {REPORT_OUT}")


if __name__ == "__main__":
    run()
