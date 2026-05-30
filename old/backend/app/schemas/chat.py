"""Request/response schemas for the chat endpoint (D7: Pydantic I/O contracts).

Citations are part of the response shape from the start (populated in Step 6 once
retrieval returns sources); kept optional now to preserve Step-2 parity.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    product_name: str
    snippet: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    session_id: str
    cached: bool = False
