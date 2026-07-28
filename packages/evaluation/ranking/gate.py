"""CI eval gate: fail the build if ranking quality regresses vs the baseline.

    uv run python -m evaluation.ranking.gate     # needs Qdrant up + OPENAI_API_KEY

Runs the production-default pipeline (hybrid, no reranker) over the golden set and compares
NDCG@3 + MRR against packages/evaluation/ranking/baseline.json (minus a tolerance). Exits non-zero
on regression so CI blocks the merge. Skips (exit 0) if no API key is configured.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from core.config import get_settings
from evaluation.ranking.run import evaluate, load_golden
from retrieval.index import load_catalog
from retrieval.store import QdrantHybridStore

BASELINE_PATH = Path(__file__).parent / "baseline.json"
GATED_METRICS = ("ndcg_at_3", "mrr")


def evaluate_gate(
    metrics: dict[str, float], baseline: dict[str, float], tolerance: float
) -> tuple[bool, list[str]]:
    """Pure gate decision: every gated metric must be within `tolerance` of its baseline."""
    ok = True
    reasons: list[str] = []
    for key in GATED_METRICS:
        floor = baseline[key] - tolerance
        passed = metrics[key] >= floor
        ok = ok and passed
        marker = "OK" if passed else "REGRESSION"
        reasons.append(
            f"{key}={metrics[key]:.4f} vs floor {floor:.4f} (baseline {baseline[key]}) {marker}"
        )
    return ok, reasons


def run_gate() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        print("eval-gate: SKIPPED (no OPENAI_API_KEY)")
        return 0

    baseline = json.loads(BASELINE_PATH.read_text())
    tolerance = float(baseline.get("tolerance", 0.05))

    catalog = load_catalog()
    store = QdrantHybridStore()
    store.index(catalog)
    rows = evaluate(load_golden(), store, {p.product_id: p.title for p in catalog}, reranker=None)
    metrics = {
        "ndcg_at_3": round(statistics.fmean(r.ndcg_at_3 for r in rows), 4),
        "mrr": round(statistics.fmean(r.rr for r in rows), 4),
    }

    ok, reasons = evaluate_gate(metrics, baseline, tolerance)
    for reason in reasons:
        print("  " + reason)
    print("eval-gate:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run_gate())
