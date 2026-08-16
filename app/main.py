"""FastAPI application entrypoint."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, conversations, health, leads
from app.api.schemas import ErrorResponse
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.rag.ingestion import ingest_knowledge_base

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    try:
        count = await ingest_knowledge_base()
        logger.info("knowledge_base_ingested_on_startup", count=count)
    except Exception as exc:
        logger.warning(
            "knowledge_base_ingestion_failed_on_startup",
            error=str(exc),
        )
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
)


@app.middleware("http")
async def security_headers_and_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("unhandled_request_error", request_id=request_id, error=str(exc))
        response = JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                request_id=request_id,
            ).model_dump(),
        )
    latency_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")

app.mount(
    "/static",
    StaticFiles(directory=f"{settings.FRONTEND_DIR}/static"),
    name="static",
)
app.mount(
    "/",
    StaticFiles(directory=settings.FRONTEND_DIR, html=True),
    name="frontend",
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=str(exc), request_id=request_id
        ).model_dump(),
    )
