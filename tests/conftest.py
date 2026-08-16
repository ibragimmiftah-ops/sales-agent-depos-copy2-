"""Shared test fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

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
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-characters-long")

from app.core.auth import create_public_chat_token
from app.core.database import get_db
from app.core.security import (
    Principal,
    create_access_token,
    get_password_hash,
)
from app.main import app
from app.models import Base, Membership, Tenant, User


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
async def test_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(id="tenant_test", name="Test Tenant", is_public=False)
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def operator_principal(
    db_session: AsyncSession, test_tenant: Tenant
) -> Principal:
    user = User(
        id="user_test_operator",
        email="operator@test.com",
        hashed_password=get_password_hash("password"),
    )
    db_session.add(user)
    await db_session.flush()
    membership = Membership(
        user_id=user.id, tenant_id=test_tenant.id, role="operator"
    )
    db_session.add(membership)
    await db_session.commit()
    token = create_access_token(
        {
            "sub": user.id,
            "tenant_id": test_tenant.id,
            "roles": ["operator"],
            "scopes": ["crm:read", "crm:write"],
        }
    )
    principal = Principal(
        user_id=user.id,
        tenant_id=test_tenant.id,
        roles=frozenset(["operator"]),
        scopes=frozenset(["crm:read", "crm:write"]),
        token=token,
    )
    return principal


@pytest_asyncio.fixture
async def admin_principal(
    db_session: AsyncSession, test_tenant: Tenant
) -> Principal:
    user = User(
        id="user_test_admin",
        email="admin@test.com",
        hashed_password=get_password_hash("password"),
    )
    db_session.add(user)
    await db_session.flush()
    membership = Membership(
        user_id=user.id, tenant_id=test_tenant.id, role="admin"
    )
    db_session.add(membership)
    await db_session.commit()
    token = create_access_token(
        {
            "sub": user.id,
            "tenant_id": test_tenant.id,
            "roles": ["admin"],
            "scopes": ["crm:read", "crm:write"],
        }
    )
    principal = Principal(
        user_id=user.id,
        tenant_id=test_tenant.id,
        roles=frozenset(["admin"]),
        scopes=frozenset(["crm:read", "crm:write"]),
        token=token,
    )
    return principal


@pytest_asyncio.fixture
async def chat_token(db_session: AsyncSession) -> str:
    return await create_public_chat_token(db_session)


@pytest_asyncio.fixture
async def client(
    tmp_path, operator_principal: Principal
) -> AsyncGenerator[TestClient, None]:
    """TestClient with an isolated SQLite DB per test and operator override."""
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
        test_client.headers["Authorization"] = f"Bearer {operator_principal.token}"
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def anonymous_client(tmp_path) -> AsyncGenerator[TestClient, None]:
    """TestClient without authentication."""
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
