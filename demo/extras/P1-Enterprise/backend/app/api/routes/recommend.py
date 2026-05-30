import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.guardrails import validate_input, validate_output
from app.core.rate_limiter import limiter
from app.core.security import get_current_user
from app.observability.cost_tracker import cost_tracker
from app.observability.logger import get_logger
from app.observability.metrics import active_recommendations
from app.rag.pipeline import stream_recommendation
from app.schemas.request import RecommendRequest

router = APIRouter(tags=["recommend"])
logger = get_logger(__name__)


@router.post(
    "/recommend",
    summary="Stream anime recommendations via Server-Sent Events",
    response_description="SSE stream of text chunks ending with [DONE]",
)
@limiter.limit("10/minute")
async def recommend(
    request: Request,          # Required parameter for SlowAPI rate limiter
    body: RecommendRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    request_id = str(uuid.uuid4())
    query = body.query.strip()
    username = current_user["username"]

    logger.info(f"request_id={request_id} user={username} query_len={len(query)}")

    blocked, reason = validate_input(query)
    if blocked:
        logger.warning(f"request_id={request_id} blocked reason={reason!r}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=reason)

    active_recommendations.inc()
    collected: list[str] = []

    def generate():
        try:
            for chunk in stream_recommendation(query):
                collected.append(chunk)
                # SSE format: each event is "data: <payload>\n\n"
                yield f"data: {chunk}\n\n"

            full_output = "".join(collected)

            # Output guardrail
            valid, msg = validate_output(full_output)
            if not valid:
                logger.warning(f"request_id={request_id} output validation failed: {msg}")
                yield f"data: [ERROR] {msg}\n\n"
                return

            cost = cost_tracker.record(query, full_output)
            logger.info(
                f"request_id={request_id} "
                f"input_tokens={cost.input_tokens} "
                f"output_tokens={cost.output_tokens} "
                f"cost_usd={cost.cost_usd}"
            )

            # Signal completion and cost metadata to the client
            yield "data: [DONE]\n\n"
            yield f"data: __cost__{cost.cost_usd}\n\n"

        except Exception as exc:
            logger.error(f"request_id={request_id} pipeline error={exc}")
            yield "data: [ERROR] An internal error occurred. Please try again.\n\n"
        finally:
            active_recommendations.dec()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for streaming
        },
    )
