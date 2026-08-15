"""Shared test fixtures."""

from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure test environment defaults before app modules are imported.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "keyword")
os.environ.setdefault("VECTOR_STORE_PROVIDER", "qdrant")

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_default_tables() -> AsyncGenerator[None, None]:
    """Create tables in the default test DB (used by unit tests)."""
    from app.core.database import engine as default_engine

    async with default_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await default_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh in-memory SQLite session for unit tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(tmp_path) -> AsyncGenerator[TestClient, None]:
    """TestClient with an isolated SQLite DB per test."""
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()
