import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import admin, auth, health, recommend
from app.core.config import get_settings
from app.core.rate_limiter import limiter
from app.observability.logger import get_logger
from app.observability.metrics import http_request_duration_seconds, http_requests_total

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    # Pre-warm the vector store so the first request is not slow
    from app.rag.vector_store import get_retriever
    get_retriever()
    logger.info("Vector store pre-warmed and ready")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Enterprise-grade anime recommendation API. "
        "Features: JWT auth, rate limiting, prompt injection defence, "
        "SSE streaming, Prometheus metrics, per-request cost tracking."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Prometheus middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next) -> Response:
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed = time.perf_counter() - start

    endpoint = request.url.path
    http_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=str(response.status_code),
    ).inc()
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(elapsed)

    return response


# ---------------------------------------------------------------------------
# Metrics endpoint (scraped by Prometheus)
# ---------------------------------------------------------------------------
@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(auth.router, prefix="/v1")
app.include_router(recommend.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
