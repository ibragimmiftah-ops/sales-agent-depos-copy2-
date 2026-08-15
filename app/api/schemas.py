"""API request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(
        default=None,
        description="Existing conversation ID; a new one is generated if omitted",
    )
    message: str = Field(..., description="User message")


class LeadUpdateRequest(BaseModel):
    fields: dict[str, Any] = Field(..., description="Fields to update")


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    checks: dict[str, str] | None = None
