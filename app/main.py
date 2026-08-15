"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import chat, conversations, health, leads
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
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(leads.router)
app.include_router(conversations.router)

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
