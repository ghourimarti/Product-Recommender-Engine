"""Application exceptions + FastAPI handlers.

Replaces the demo's ``utils/custom_exception.py``. Keeps error responses consistent and
avoids leaking internals to clients (the trace goes to logs, not the response body).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.observability.logger import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base for expected application errors."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class BudgetExceededError(AppError):
    status_code = 429
    code = "budget_exceeded"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        logger.warning("app_error: %s", exc.message)
        return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "detail": exc.message})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled_error")
        return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "Unexpected error"})
