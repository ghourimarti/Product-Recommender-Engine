"""CI eval gate for the shipped /aggregate ranking path.

    uv run python -m evaluation.aggregator.gate     # offline: 0 SerpApi searches, no API key

Two independent guards:

1. **No regression** — NDCG@3 and MRR must stay within `tolerance` of the frozen baseline.
2. **Still beats Google** — our ordering must outrank Google Shopping's own `position` order.
   This is the product's entire value claim; if it fails, the aggregator has no reason to exist,
   so the build should fail rather than ship a re-ranker that re-ranks for the worse.

Unlike the other gates this needs no services and no keys (it reads recorded fixtures), so it
runs on every PR.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluation.aggregator.run import aggregate_metrics, evaluate

BASELINE_PATH = Path(__file__).parent / "baseline.json"
GATED_METRICS = ("ndcg_at_3", "mrr")


def evaluate_gate(
    metrics: dict[str, float], baseline: dict[str, float], tolerance: float
) -> tuple[bool, list[str]]:
    """Pure gate decision — no I/O, so it is unit-testable."""
    ok = True
    reasons: list[str] = []

    for key in GATED_METRICS:
        floor = baseline[key] - tolerance
        passed = metrics[key] >= floor
        ok = ok and passed
        reasons.append(
            f"{key}={metrics[key]:.4f} vs floor {floor:.4f} "
            f"(baseline {baseline[key]}) {'OK' if passed else 'REGRESSION'}"
        )

    if baseline.get("must_beat_google"):
        beats = (
            metrics["ndcg_at_3"] > metrics["google_ndcg_at_3"]
            and metrics["mrr"] >= metrics["google_mrr"]
        )
        ok = ok and beats
        reasons.append(
            f"beats_google: ours NDCG@3={metrics['ndcg_at_3']:.4f}/MRR={metrics['mrr']:.4f} vs "
            f"google NDCG@3={metrics['google_ndcg_at_3']:.4f}/MRR={metrics['google_mrr']:.4f} "
            f"{'OK' if beats else 'FAIL — our ranking is no better than Google’s'}"
        )
    return ok, reasons


def run_gate() -> int:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    tolerance = float(baseline.get("tolerance", 0.05))
    metrics = aggregate_metrics(evaluate())

    ok, reasons = evaluate_gate(metrics, baseline, tolerance)
    for reason in reasons:
        print("  " + reason)
    print("aggregator-eval-gate:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run_gate())
