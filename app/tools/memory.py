"""save_memory tool — persists important facts to the lead profile."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.crm import CRMService
from app.tools.base import Tool, ToolContext, register_tool


class SaveMemoryInput(BaseModel):
    lead_id: str = Field(...)
    fields: dict[str, Any] = Field(..., description="Important facts to remember")


class SaveMemoryTool(Tool):
    name = "save_memory"
    description = "Save important information about the lead to long-term memory."
    input_schema = SaveMemoryInput

    async def execute(self, context: ToolContext, arguments: SaveMemoryInput) -> dict[str, Any]:
        lead = await CRMService.update_lead(
            context.session, arguments.lead_id, arguments.fields
        )
        await CRMService.append_event(
            context.session,
            lead.id,
            "memory_saved",
            {"fields": list(arguments.fields.keys())},
        )
        return {"lead_id": lead.id, "saved_fields": list(arguments.fields.keys())}


register_tool(SaveMemoryTool())
