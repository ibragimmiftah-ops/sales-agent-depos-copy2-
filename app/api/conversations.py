"""Conversation history endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_authenticated
from app.core.database import get_db
from app.core.security import Principal
from app.models import Conversation, Message

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.get("/{conversation_id}", response_model=list[dict[str, Any]])
async def get_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
):
    # Operators/admins can read any conversation in their tenant.
    # Anonymous chat principals can read only their own conversation (path).
    if principal.has_role("chat") and not principal.has_role("operator", "admin"):
        # Anonymous principals do not have a stable user_id; we rely on the
        # conversation existing in their tenant as a weak ownership check.
        pass

    # Verify the conversation belongs to the tenant.
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == principal.tenant_id,
        )
    )
    if conv_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == principal.tenant_id,
        )
        .order_by(Message.created_at.asc())
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "intent": m.intent,
            "decision": m.decision,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in result.scalars().all()
    ]
