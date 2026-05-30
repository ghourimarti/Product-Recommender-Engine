"""FastAPI application entrypoint (Step 2 — replaces the Step-1 Flask app).

Async + Pydantic I/O + readiness-gated RAG. The lifespan builds the RagService but does
NOT crash the process if it can't (missing keys / downstream down) — instead the app boots
and ``/readyz`` reports 503 until the service is up. This is the production behavior K8s
expects (liveness stays green, readiness gates traffic).

Implements Decision 7. Run: ``uvicorn app.main:app --host 0.0.0.0 --port 8000``.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.observability.logger import configure_logging, get_logger
from app.observability.metrics import MetricsMiddleware
from app.observability.tracing import configure_tracing
from app.rag.service import RagService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    rag = RagService()
    try:
        rag.build()
    except Exception:  # noqa: BLE001 - boot must not crash on downstream/key failure
        logger.exception("rag_build_failed_boot_continues")
    app.state.rag_service = rag
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Product Recommender API",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(MetricsMiddleware)
    configure_tracing(app)  # no-op unless OTel is enabled + configured
    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Binding all interfaces is intentional inside the container; exposure is controlled by the
    # K8s NetworkPolicy (default-deny) + ingress, not the bind address.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.environment == "local")  # nosec B104
