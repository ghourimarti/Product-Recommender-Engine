"""
RAG evaluation using RAGAS.

Run:
    python -m tests.evaluation.eval_ragas

Requires a populated ChromaDB and a valid GROQ_API_KEY.
Used in CI via .github/workflows/rag-eval.yml on PRs that touch rag/ code.

Exit codes:
    0 — all metrics above threshold
    1 — one or more metrics below threshold
"""

import json
import sys
from pathlib import Path

from datasets import Dataset
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness

from app.core.config import get_settings
from app.rag.pipeline import get_chain
from app.rag.vector_store import get_retriever

settings = get_settings()

THRESHOLDS = {
    "faithfulness": 0.65,
    "answer_relevancy": 0.65,
}


def run_evaluation(num_samples: int = 20) -> bool:
    golden_path = Path(__file__).parent / "golden_dataset.json"
    with open(golden_path) as f:
        dataset_json = json.load(f)

    samples = dataset_json["samples"][:num_samples]
    retriever = get_retriever()
    chain = get_chain()

    questions, answers, contexts, ground_truths = [], [], [], []

    print(f"Running evaluation on {len(samples)} samples...")
    for i, item in enumerate(samples, 1):
        q = item["question"]
        docs = retriever.invoke(q)
        ctx = [doc.page_content for doc in docs]
        answer = chain.invoke(q)

        questions.append(q)
        answers.append(answer)
        contexts.append(ctx)
        ground_truths.append(item["ground_truth"])

        print(f"  [{i}/{len(samples)}] {q[:60]}...")

    eval_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.MODEL_NAME, temperature=0)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    result = evaluate(
        eval_dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )

    scores = result.to_pandas().mean(numeric_only=True)

    print("\n" + "=" * 50)
    print("RAG Evaluation Results")
    print("=" * 50)

    failed_metrics = []
    for metric, threshold in THRESHOLDS.items():
        score = float(scores.get(metric, 0.0))
        status = "PASS" if score >= threshold else "FAIL"
        icon = "✓" if score >= threshold else "✗"
        print(f"  {icon} {metric:<25} {score:.3f}  (threshold={threshold})  [{status}]")
        if score < threshold:
            failed_metrics.append(metric)

    print("=" * 50)

    if failed_metrics:
        print(f"\nFAILED metrics: {failed_metrics}")
        print("RAG quality is below acceptable thresholds. Review retrieval and prompt.\n")
        return False

    print("\nAll metrics passed. RAG pipeline quality is acceptable.\n")
    return True


if __name__ == "__main__":
    passed = run_evaluation()
    sys.exit(0 if passed else 1)
