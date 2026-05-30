"""Self-hosted embedding microservice (Decision 12).

Serves bge-base embeddings over HTTP so the backend doesn't depend on a hosted embedding
API (cost + data-in-VPC for GDPR). Uses fastembed (ONNX, no torch) so it runs on CPU.

EMBEDDING_STUB=1 returns deterministic vectors without downloading a model — used by tests
and CI smoke; production leaves it unset and serves the real model.
"""
from __future__ import annotations

import hashlib
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
DIM = int(os.getenv("EMBEDDING_DIM", "768"))
STUB = os.getenv("EMBEDDING_STUB", "") == "1"

app = FastAPI(title="Embedding Service", version="0.1.0")
_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def _stub_vec(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    raw = [digest[i % len(digest)] / 255.0 for i in range(DIM)]
    norm = sum(x * x for x in raw) ** 0.5 or 1.0
    return [x / norm for x in raw]


def _embed(texts: list[str]) -> list[list[float]]:
    if STUB:
        return [_stub_vec(t) for t in texts]
    return [list(map(float, v)) for v in _get_model().embed(texts)]


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    model: str
    dim: int


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {"status": "ok", "model": MODEL_NAME, "stub": STUB}


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    vectors = _embed(req.texts)
    return EmbedResponse(vectors=vectors, model=MODEL_NAME, dim=len(vectors[0]))
