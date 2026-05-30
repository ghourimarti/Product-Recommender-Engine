# syntax=docker/dockerfile:1
# Multi-stage, non-root image for the FastAPI service. Build context = repo root.

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
# Deps only (project packages installed editable, referencing /app/packages).
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
RUN uv sync --no-dev --frozen

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
RUN useradd -m -u 10001 appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY packages/ ./packages/
COPY apps/api/ ./apps/api/
COPY data/ ./data/
USER appuser
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--app-dir", "apps", "--host", "0.0.0.0", "--port", "8080"]
