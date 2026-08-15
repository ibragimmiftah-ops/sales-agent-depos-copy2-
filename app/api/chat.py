"""Chat endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import SalesAgent, get_sales_agent
from app.agent.schemas import AgentState
from app.api.schemas import ChatRequest
from app.core.database import get_db

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=AgentState)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    agent: SalesAgent = Depends(get_sales_agent),
) -> AgentState:
    conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    return await agent.handle(db, conversation_id, request.message)
