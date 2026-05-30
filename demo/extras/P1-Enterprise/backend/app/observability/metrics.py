from prometheus_client import Counter, Histogram, Gauge

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

rag_retrieval_duration_seconds = Histogram(
    "rag_retrieval_duration_seconds",
    "Vector store retrieval duration in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

rag_requests_total = Counter(
    "rag_requests_total",
    "Total RAG recommendation requests",
    ["status"],  # started | success | error
)

tokens_used_total = Counter(
    "tokens_used_total",
    "Total tokens consumed",
    ["type"],  # input | output
)

cost_usd_total = Counter(
    "cost_usd_total",
    "Cumulative LLM cost in USD",
)

guardrail_violations_total = Counter(
    "guardrail_violations_total",
    "Total guardrail violations by type",
    ["type"],
)

active_recommendations = Gauge(
    "active_recommendations",
    "Number of recommendations currently being streamed",
)
