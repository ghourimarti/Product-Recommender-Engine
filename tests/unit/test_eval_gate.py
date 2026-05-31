"""Unit tests for the CI eval-gate decision logic (Step 18). Pure, no services."""

from __future__ import annotations

from evaluation.ranking.gate import evaluate_gate

BASELINE = {"ndcg_at_3": 0.80, "mrr": 0.83}
TOLERANCE = 0.05


def test_gate_passes_within_tolerance() -> None:
    ok, _ = evaluate_gate({"ndcg_at_3": 0.78, "mrr": 0.80}, BASELINE, TOLERANCE)
    assert ok


def test_gate_passes_when_improved() -> None:
    ok, _ = evaluate_gate({"ndcg_at_3": 0.90, "mrr": 0.91}, BASELINE, TOLERANCE)
    assert ok


def test_gate_fails_on_regression() -> None:
    ok, reasons = evaluate_gate({"ndcg_at_3": 0.70, "mrr": 0.83}, BASELINE, TOLERANCE)
    assert not ok
    assert any("ndcg_at_3" in r and "REGRESSION" in r for r in reasons)
