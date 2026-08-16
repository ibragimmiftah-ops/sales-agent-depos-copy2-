"""API request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(
        default=None,
        max_length=64,
        description="Existing conversation ID; a new one is generated if omitted",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message",
    )


class LeadUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    industry: str | None = Field(default=None, max_length=128)
    company_size: str | None = Field(default=None, max_length=64)
    business_problem: str | None = Field(default=None, max_length=4000)
    desired_solution: str | None = Field(default=None, max_length=1000)
    current_process: str | None = Field(default=None, max_length=4000)
    current_software: str | None = Field(default=None, max_length=255)
    channels: list[str] | None = Field(default=None, max_length=20)
    monthly_leads: int | None = Field(default=None, ge=0, le=10_000_000)
    monthly_customer_requests: int | None = Field(default=None, ge=0, le=10_000_000)
    budget_range: str | None = Field(default=None, max_length=255)
    deadline: str | None = Field(default=None, max_length=64)
    decision_maker: bool | None = Field(default=None)
    urgency: str | None = Field(default=None, max_length=64)
    additional_notes: str | None = Field(default=None, max_length=4000)
    next_best_action: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    checks: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    error: str
    request_id: str
    detail: dict[str, Any] | None = None
