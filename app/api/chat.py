"""Chat endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import SalesAgent, get_sales_agent
from app.agent.schemas import AgentState
from app.api.schemas import ChatRequest
from app.core.auth import get_principal
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ServiceError
from app.core.limits import RateLimiter
from app.core.logging import get_logger
from app.core.security import Principal

router = APIRouter(prefix="/v1", tags=["chat"])
logger = get_logger(__name__)
rate_limiter = RateLimiter(
    key_prefix="chat",
    max_requests=settings.RATE_LIMIT_CHAT_PER_MINUTE,
    window_seconds=60,
)


@router.post("/chat", response_model=AgentState)
async def chat(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    agent: SalesAgent = Depends(get_sales_agent),
    principal: Principal = Depends(get_principal),
) -> AgentState:
    # Enforce public chat role cannot access other endpoints; chat endpoint is fine.
    await rate_limiter.check(request, principal)

    if not principal.has_scope("chat:send") and not principal.has_role(
        "operator", "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat permission required",
        )

    conversation_id = payload.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    try:
        return await agent.handle(
            db,
            conversation_id,
            payload.message,
            principal=principal,
            run_id=run_id,
        )
    except ServiceError as exc:
        logger.error("chat_service_error", run_id=run_id, error=exc.message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except Exception as exc:
        logger.error("chat_unhandled_error", run_id=run_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error",
        ) from exc
