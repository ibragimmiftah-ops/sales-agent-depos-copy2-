"""FastAPI authentication/authorization dependencies."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import (
    Principal,
    create_access_token,
    principal_from_token,
    verify_password,
)
from app.models import Tenant, User

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


async def _get_or_create_public_tenant(session: AsyncSession) -> Tenant:
    result = await session.execute(
        select(Tenant).where(Tenant.is_public.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(id="tenant_public", name="Public widget tenant", is_public=True)
        session.add(tenant)
        await session.flush()
    return tenant


async def _public_principal(session: AsyncSession) -> Principal:
    tenant = await _get_or_create_public_tenant(session)
    return Principal(
        user_id=None,
        tenant_id=tenant.id,
        roles=frozenset(["chat"]),
        scopes=frozenset(["chat:send"]),
        is_anonymous=True,
    )


def _require_auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )


async def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Resolve principal from Bearer token or anonymous chat scope.

    Anonymous chat is allowed only for POST /api/v1/chat when no credentials
    are provided. All other routes require a valid JWT.
    """
    token = credentials.credentials if credentials else None

    if token:
        principal = principal_from_token(token)
        if principal is None:
            raise _require_auth_exception()
        return principal

    # Allow anonymous chat only on the chat endpoint.
    if request.method == "POST" and request.url.path.endswith("/chat"):
        return await _public_principal(db)

    raise _require_auth_exception()


async def require_authenticated(
    principal: Principal = Depends(get_principal),
) -> Principal:
    if principal.is_anonymous:
        raise _require_auth_exception()
    return principal


def require_roles(*roles: str):
    async def checker(principal: Principal = Depends(require_authenticated)) -> Principal:
        if not principal.has_role(*roles):
            raise _forbidden_exception()
        return principal
    return checker


async def create_operator_token(
    session: AsyncSession,
    email: str,
    password: str,
) -> str | None:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    # Eager load memberships.
    await session.refresh(user, ["memberships"])
    if not user.memberships:
        return None
    membership = user.memberships[0]
    return create_access_token(
        {
            "sub": user.id,
            "tenant_id": membership.tenant_id,
            "roles": [membership.role],
            "scopes": ["crm:read", "crm:write"] if membership.role in ("admin", "operator") else [],
        }
    )


async def create_public_chat_token(session: AsyncSession) -> str:
    tenant = await _get_or_create_public_tenant(session)
    return create_access_token(
        {
            "sub": f"anon_{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant.id,
            "roles": ["chat"],
            "scopes": ["chat:send"],
            "anonymous": True,
        },
        expires_delta=timedelta(hours=4),
    )
