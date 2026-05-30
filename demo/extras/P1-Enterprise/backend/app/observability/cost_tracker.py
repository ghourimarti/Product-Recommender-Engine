import threading
from dataclasses import dataclass

from app.core.config import get_settings
from app.observability.metrics import cost_usd_total, tokens_used_total

settings = get_settings()


@dataclass
class RequestCost:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        input_cost = (self.input_tokens / 1_000_000) * settings.COST_INPUT_PER_M_TOKENS
        output_cost = (self.output_tokens / 1_000_000) * settings.COST_OUTPUT_PER_M_TOKENS
        return round(input_cost + output_cost, 8)


class CostTracker:
    """Thread-safe in-memory cost and token tracker.

    Uses character-based token estimation (~4 chars/token) to avoid
    importing tiktoken and keep the dependency footprint small.
    For production replace with exact token counts from the LLM response.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_cost: float = 0.0
        self._total_requests: int = 0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def record(self, input_text: str, output_text: str) -> RequestCost:
        cost = RequestCost(
            input_tokens=self._estimate_tokens(input_text),
            output_tokens=self._estimate_tokens(output_text),
        )
        tokens_used_total.labels(type="input").inc(cost.input_tokens)
        tokens_used_total.labels(type="output").inc(cost.output_tokens)
        cost_usd_total.inc(cost.cost_usd)

        with self._lock:
            self._total_cost += cost.cost_usd
            self._total_requests += 1
            self._total_input_tokens += cost.input_tokens
            self._total_output_tokens += cost.output_tokens

        return cost

    def get_summary(self) -> dict:
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "total_cost_usd": round(self._total_cost, 6),
                "avg_cost_per_request_usd": round(
                    self._total_cost / max(1, self._total_requests), 6
                ),
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
            }


# Module-level singleton
cost_tracker = CostTracker()
