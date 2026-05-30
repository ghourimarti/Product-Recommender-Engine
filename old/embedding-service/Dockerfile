# Embedding microservice (Decision 12). fastembed is ONNX/CPU -> no GPU base needed.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

FROM base AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
WORKDIR /app
RUN useradd --create-home --uid 10002 appuser
COPY --from=builder /install /usr/local
COPY app.py .
USER appuser
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/healthz').status==200 else 1)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
