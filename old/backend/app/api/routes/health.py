"""Liveness and readiness probes (K8s-ready, used in Step 20)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_rag_service
from app.rag.service import RagService

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: process is up. Never depends on downstreams."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response, rag: RagService = Depends(get_rag_service)) -> dict[str, object]:
    """Readiness: are we able to serve traffic? Reflects RAG availability."""
    if not rag.ready:
        response.status_code = 503
        return {"status": "not_ready", "rag": False}
    return {"status": "ready", "rag": True}
