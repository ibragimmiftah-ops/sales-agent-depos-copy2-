"""Calendar tools: get_available_slots and book_meeting."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import ToolError
from app.services.policy import LeadPolicy
from app.tools.base import Tool, ToolContext, register_tool


class GetAvailableSlotsInput(BaseModel):
    tenant_id: str = Field(...)
    timezone: str = Field(default=settings.DEFAULT_TIMEZONE)
    date_from: str = Field(..., description="Start date YYYY-MM-DD")
    date_to: str = Field(..., description="End date YYYY-MM-DD")
    duration_minutes: int = Field(default=settings.SLOT_DURATION_MINUTES)


class GetAvailableSlotsTool(Tool[GetAvailableSlotsInput]):
    name = "get_available_slots"
    description = "Get available meeting slots in a date range."
    input_schema = GetAvailableSlotsInput

    async def execute(
        self, context: ToolContext, arguments: GetAvailableSlotsInput
    ) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            raise ToolError("Tenant mismatch")
        slots = await context.calendar_service.get_available_slots(
            context.session,
            tenant_id=context.principal.tenant_id,
            timezone=arguments.timezone,
            date_from=arguments.date_from,
            date_to=arguments.date_to,
            duration_minutes=arguments.duration_minutes,
            exclude_lead_id=context.principal.user_id,
        )
        return {"slots": slots}


class BookMeetingInput(BaseModel):
    lead_id: str = Field(...)
    tenant_id: str = Field(...)
    datetime: str = Field(..., description="ISO 8601 datetime")
    duration_minutes: int = Field(default=settings.SLOT_DURATION_MINUTES)
    name: str | None = None
    email: str | None = None
    timezone: str | None = None
    offered_meeting_id: str | None = None


class BookMeetingTool(Tool[BookMeetingInput]):
    name = "book_meeting"
    description = "Book a meeting for a lead."
    input_schema = BookMeetingInput

    async def execute(self, context: ToolContext, arguments: BookMeetingInput) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            raise ToolError("Tenant mismatch")

        from sqlalchemy import select

        from app.models import Lead

        lead_result = await context.session.execute(
            select(Lead).where(
                Lead.id == arguments.lead_id,
                Lead.tenant_id == context.principal.tenant_id,
            )
        )
        lead = lead_result.scalar_one_or_none()
        if lead is None:
            raise ToolError(f"Lead {arguments.lead_id} not found")

        if not LeadPolicy.is_meeting_eligible(lead):
            reasons = LeadPolicy.meeting_eligibility_reasons(lead)
            return {
                "success": False,
                "error": "Lead is not eligible for booking",
                "reasons": reasons,
            }

        name = arguments.name or lead.name or "Unknown"
        email = arguments.email or lead.email or ""
        meeting = await context.calendar_service.book_meeting(
            context.session,
            tenant_id=context.principal.tenant_id,
            lead_id=arguments.lead_id,
            datetime_str=arguments.datetime,
            duration_minutes=arguments.duration_minutes,
            name=name,
            email=email,
            timezone=arguments.timezone,
            offered_meeting_id=arguments.offered_meeting_id,
        )
        return {
            "success": True,
            "meeting_id": meeting.id,
            "meeting_url": meeting.meeting_url,
            "datetime": meeting.datetime.isoformat(),
        }


register_tool(GetAvailableSlotsTool())
register_tool(BookMeetingTool())
