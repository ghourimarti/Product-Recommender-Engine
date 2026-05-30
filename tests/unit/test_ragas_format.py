"""Unit test for RAGAS answer formatting + golden loading (Step 7). Pure, no services."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.models import Explanation, ExplanationSet
from evaluation.ragas.run import JudgeScores, format_answer, load_golden


def test_format_answer_includes_summary_and_reasons() -> None:
    expl = ExplanationSet(
        summary="Two solid picks.",
        explanations=[
            Explanation(product_id="A", reason="great bass"),
            Explanation(product_id="B", reason="long battery"),
        ],
    )
    answer = format_answer(expl)
    assert "Two solid picks." in answer
    assert "A: great bass" in answer
    assert "B: long battery" in answer


def test_format_answer_handles_no_explanations() -> None:
    assert format_answer(ExplanationSet(summary="None found.", explanations=[])) == "None found."


def test_load_golden_has_queries() -> None:
    golden = load_golden()
    assert len(golden) >= 5
    assert all(item.query.strip() for item in golden)


def test_judge_scores_bounds() -> None:
    JudgeScores(faithfulness=0.9, answer_relevancy=0.8, context_precision=0.7)  # ok
    with pytest.raises(ValidationError):
        JudgeScores(faithfulness=1.5, answer_relevancy=0.8, context_precision=0.7)
