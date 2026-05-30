"""Ranking-quality metrics for the recommender eval (Step 5). Pure, binary-relevance.

- Recall@k : fraction of the relevant set retrieved in the top-k.
- NDCG@k   : ranking quality (position-discounted), normalized to [0, 1].
- MRR      : reciprocal rank of the first relevant item over the full ranking.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = set(ranked_ids[:k])
    return len(top_k & relevant) / len(relevant)


def precision_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = set(ranked_ids[:k])
    return len(top_k & relevant) / k


def ndcg_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, pid in enumerate(ranked_ids[:k]) if pid in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def reciprocal_rank(ranked_ids: Sequence[str], relevant: set[str]) -> float:
    for i, pid in enumerate(ranked_ids):
        if pid in relevant:
            return 1.0 / (i + 1)
    return 0.0
