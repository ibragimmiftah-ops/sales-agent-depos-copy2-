"""save_memory tool — persists important facts to the lead profile."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.exceptions import ToolError
from app.services.crm import AGENT_UPDATABLE_FIELDS, CRMService
from app.tools.base import Tool, ToolContext, register_tool


class SaveMemoryInput(BaseModel):
    lead_id: str = Field(...)
    tenant_id: str = Field(...)
    fields: dict[str, Any] = Field(..., description="Important facts to remember")

    @field_validator("fields")
    @classmethod
    def _validate_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        for key in v:
            if key not in AGENT_UPDATABLE_FIELDS:
                raise ValueError(f"Field '{key}' is not allowed for memory updates")
        return v


class SaveMemoryTool(Tool[SaveMemoryInput]):
    name = "save_memory"
    description = "Save important information about the lead to long-term memory."
    input_schema = SaveMemoryInput

    async def execute(self, context: ToolContext, arguments: SaveMemoryInput) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            raise ToolError("Tenant mismatch")
        lead = await CRMService.update_lead(
            context.session,
            arguments.lead_id,
            tenant_id=context.principal.tenant_id,
            fields=arguments.fields,
            allowed_fields=AGENT_UPDATABLE_FIELDS,
        )
        await CRMService.append_event(
            context.session,
            lead.id,
            tenant_id=context.principal.tenant_id,
            event_type="memory_saved",
            payload={"fields": list(arguments.fields.keys())},
        )
        return {"lead_id": lead.id, "saved_fields": list(arguments.fields.keys())}


register_tool(SaveMemoryTool())
