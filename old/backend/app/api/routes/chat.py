"""Chat endpoints: JSON (/chat, parity) and SSE token streaming (/chat/stream, Step 9)."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_budget, get_rag_service
from app.core.budget import TokenBudget, budget_guard
from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.guardrails import check_user_input
from app.core.rate_limiter import rate_limit
from app.core.security import Principal, get_current_user
from app.observability.cost import estimate_tokens, record_usage
from app.rag.service import RagService
from app.schemas.chat import ChatRequest, ChatResponse

# Rate limit + budget guard apply to every chat route (Decision 20).
router = APIRouter(tags=["chat"], dependencies=[Depends(rate_limit), Depends(budget_guard)])


def _resolve_session(user: Principal, session_id: str | None) -> tuple[str, str, bool]:
    """Return (client_sid, effective_sid, first_turn).

    - client_sid: the id we hand back to the client (no user sub leaked).
    - effective_sid: namespaced per-user so two users' identical session_ids never collide
      and history stays isolated (D9).
    - first_turn: no session_id supplied -> standalone question, eligible for caching.
    """
    first_turn = session_id is None
    client_sid = session_id or uuid.uuid4().hex
    return client_sid, f"{user.sub}:{client_sid}", first_turn


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    rag: RagService = Depends(get_rag_service),
    user: Principal = Depends(get_current_user),
    budget: TokenBudget = Depends(get_budget),
) -> ChatResponse:
    check_user_input(payload.message)
    client_sid, effective, first_turn = _resolve_session(user, payload.session_id)
    resp = rag.answer(message=payload.message, session_id=effective, use_cache=first_turn)

    # Token + cost accounting -> Prometheus + daily budget (D17/D20). Real token counts come
    # from LLM metadata in prod; estimated here. Cached answers cost ~0 (no generation).
    if not resp.cached:
        record_usage(
            budget,
            None if user.anonymous else user.sub,
            settings.rag_model,
            estimate_tokens(payload.message),
            estimate_tokens(resp.answer),
        )
    return resp.model_copy(update={"session_id": client_sid})  # never leak the user-scoped id


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    rag: RagService = Depends(get_rag_service),
    user: Principal = Depends(get_current_user),
) -> EventSourceResponse:
    """SSE token stream. Client cancellation is handled by the ASGI server closing the
    generator; the frontend uses AbortController (Decision 8). Retry is client-side."""
    check_user_input(payload.message)
    client_sid, effective, _ = _resolve_session(user, payload.session_id)

    async def event_gen():
        try:
            async for ev in rag.astream(payload.message, effective):
                data = {**ev.data, "session_id": client_sid} if ev.event == "done" else ev.data
                yield {"event": ev.event, "data": json.dumps(data)}
        except ServiceUnavailableError as exc:
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
        except Exception:  # noqa: BLE001 - degrade, don't fail (D21)
            yield {"event": "error", "data": json.dumps({"detail": "temporary error, please retry"})}

    return EventSourceResponse(event_gen())
