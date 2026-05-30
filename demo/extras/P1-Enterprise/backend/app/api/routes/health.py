import time

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.response import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()
_start_time = time.time()


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@router.get("/ready", summary="Readiness probe — verifies ChromaDB is accessible")
async def ready() -> dict:
    try:
        from app.rag.vector_store import get_retriever
        get_retriever()
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Vector store not ready: {exc}")
