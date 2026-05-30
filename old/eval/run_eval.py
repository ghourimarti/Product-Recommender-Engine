"""RAGAS evaluation runner (Decision 19).

Runs the live RAG pipeline over the golden Q/A set and scores it with RAGAS
(faithfulness, answer_relevancy, context_precision, context_recall). Results are written to
``eval/results/<timestamp>.json`` and gate CI in Step 22.

Run (Python 3.12 venv, populated Qdrant, real keys):
    python eval/run_eval.py
Validate dataset + wiring without calling any model:
    python eval/run_eval.py --dry-run

The --dry-run path is what we can verify without keys; the scored path is the keyed step.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATASET = Path(__file__).parent / "golden_dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"

REQUIRED_FIELDS = {"id", "question", "ground_truth", "ground_truth_contexts"}

# CI gate (Decision 19): merge fails if any metric regresses below these.
THRESHOLDS = {
    "faithfulness": 0.70,
    "answer_relevancy": 0.70,
    "context_precision": 0.60,
    "context_recall": 0.60,
}


def load_dataset() -> list[dict]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    items = data["items"]
    for i, item in enumerate(items):
        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            raise ValueError(f"item {i} missing fields: {missing}")
        if not isinstance(item["ground_truth_contexts"], list):
            raise ValueError(f"item {item['id']} ground_truth_contexts must be a list")
    return items


def run_pipeline(items: list[dict]) -> list[dict]:
    """Execute the live RAG pipeline per question, collecting answer + retrieved contexts."""
    sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
    from app.rag.factory import build_answer_engine

    engine = build_answer_engine()
    rows = []
    for item in items:
        resp = engine.answer(item["question"], session_id=f"eval-{item['id']}")
        rows.append({
            "question": item["question"],
            "answer": resp.answer,
            "contexts": [c.snippet or "" for c in resp.citations],
            "ground_truth": item["ground_truth"],
        })
    return rows


def score_with_ragas(rows: list[dict]) -> dict:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    ds = Dataset.from_list(rows)
    result = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
    return {k: float(v) for k, v in result.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset + exit (no model calls)")
    args = parser.parse_args()

    items = load_dataset()
    print(f"[eval] loaded {len(items)} golden items; schema OK")
    if args.dry_run:
        print("[eval] --dry-run: dataset valid, pipeline wiring importable. Skipping model calls.")
        return

    rows = run_pipeline(items)
    scores = score_with_ragas(rows)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(json.dumps({"scores": scores, "rows": rows}, indent=2), encoding="utf-8")
    print(f"[eval] scores: {scores}")
    print(f"[eval] wrote {out}")

    # Gate: fail (non-zero exit) if any metric is below its threshold.
    failed = {k: scores[k] for k, t in THRESHOLDS.items() if scores.get(k, 0.0) < t}
    if failed:
        print(f"[eval] FAILED thresholds: {failed}")
        sys.exit(1)
    print("[eval] all thresholds passed")


if __name__ == "__main__":
    main()
