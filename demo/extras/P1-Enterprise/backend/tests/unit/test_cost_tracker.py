from app.observability.cost_tracker import CostTracker


def test_token_estimation():
    tracker = CostTracker()
    # 4 chars ≈ 1 token
    tokens = tracker._estimate_tokens("a" * 400)
    assert tokens == 100


def test_cost_calculation():
    tracker = CostTracker()
    cost = tracker.record("a" * 4000, "b" * 4000)  # 1000 input tokens, 1000 output tokens
    # 1000/1M * 0.05 + 1000/1M * 0.08 = 0.00005 + 0.00008 = 0.00013
    assert cost.cost_usd > 0
    assert cost.input_tokens == 1000
    assert cost.output_tokens == 1000


def test_summary_accumulates():
    tracker = CostTracker()
    tracker.record("hello world query", "here are three recommendations...")
    tracker.record("another query about action anime", "naruto is a great choice...")
    summary = tracker.get_summary()
    assert summary["total_requests"] == 2
    assert summary["total_cost_usd"] > 0
    assert summary["avg_cost_per_request_usd"] > 0


def test_summary_empty_state():
    tracker = CostTracker()
    summary = tracker.get_summary()
    assert summary["total_requests"] == 0
    assert summary["total_cost_usd"] == 0.0
    assert summary["avg_cost_per_request_usd"] == 0.0
