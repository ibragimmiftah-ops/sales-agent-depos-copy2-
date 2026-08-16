"""CRM tools: create_lead, update_lead, get_lead."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.exceptions import ToolError
from app.models import Lead
from app.services.crm import OPERATOR_UPDATABLE_FIELDS, CRMService
from app.tools.base import Tool, ToolContext, register_tool


def _lead_to_dict(lead: Lead) -> dict[str, Any]:
    return {
        "lead_id": lead.id,
        "tenant_id": lead.tenant_id,
        "conversation_id": lead.conversation_id,
        "name": lead.name,
        "company": lead.company,
        "email": lead.email,
        "phone": lead.phone,
        "industry": lead.industry,
        "company_size": lead.company_size,
        "business_problem": lead.business_problem,
        "desired_solution": lead.desired_solution,
        "current_process": lead.current_process,
        "current_software": lead.current_software,
        "channels": lead.channels,
        "monthly_leads": lead.monthly_leads,
        "monthly_customer_requests": lead.monthly_customer_requests,
        "budget_range": lead.budget_range,
        "deadline": lead.deadline,
        "decision_maker": lead.decision_maker,
        "urgency": lead.urgency,
        "additional_notes": lead.additional_notes,
        "lead_score": lead.lead_score,
        "lead_quality": lead.lead_quality,
        "status": lead.status,
        "next_best_action": lead.next_best_action,
        "meeting_datetime": lead.meeting_datetime.isoformat() if lead.meeting_datetime else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


class CreateLeadInput(BaseModel):
    tenant_id: str = Field(...)
    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    industry: str | None = None
    company_size: str | None = None
    business_problem: str | None = None
    desired_solution: str | None = None
    current_process: str | None = None
    current_software: str | None = None
    channels: list[str] | None = None
    monthly_leads: int | None = None
    monthly_customer_requests: int | None = None
    budget_range: str | None = None
    deadline: str | None = None
    decision_maker: bool | None = None
    urgency: str | None = None
    additional_notes: str | None = None


class CreateLeadTool(Tool[CreateLeadInput]):
    name = "create_lead"
    description = "Create a new lead in the CRM."
    input_schema = CreateLeadInput

    async def execute(self, context: ToolContext, arguments: CreateLeadInput) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            raise ToolError("Tenant mismatch")
        data = arguments.model_dump(exclude={"tenant_id"}, exclude_unset=True, exclude_none=True)
        lead = await CRMService.create_lead(
            context.session, data, tenant_id=context.principal.tenant_id
        )
        return {"lead_id": lead.id, "lead": _lead_to_dict(lead)}


class UpdateLeadInput(BaseModel):
    lead_id: str = Field(..., description="Lead ID")
    tenant_id: str = Field(...)
    fields: dict[str, Any] = Field(..., description="Fields to update")

    @field_validator("fields")
    @classmethod
    def _validate_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        for key in v:
            if key not in OPERATOR_UPDATABLE_FIELDS:
                raise ValueError(f"Field '{key}' is not allowed")
        return v


class UpdateLeadTool(Tool[UpdateLeadInput]):
    name = "update_lead"
    description = "Update an existing lead's fields in the CRM."
    input_schema = UpdateLeadInput

    async def execute(self, context: ToolContext, arguments: UpdateLeadInput) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            raise ToolError("Tenant mismatch")
        lead = await CRMService.update_lead(
            context.session,
            arguments.lead_id,
            tenant_id=context.principal.tenant_id,
            fields=arguments.fields,
        )
        return {"lead_id": lead.id, "lead": _lead_to_dict(lead)}


class GetLeadInput(BaseModel):
    lead_id: str = Field(..., description="Lead ID")
    tenant_id: str = Field(...)


class GetLeadTool(Tool[GetLeadInput]):
    name = "get_lead"
    description = "Retrieve a lead from the CRM."
    input_schema = GetLeadInput

    async def execute(self, context: ToolContext, arguments: GetLeadInput) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            raise ToolError("Tenant mismatch")
        lead = await CRMService.get_lead(
            context.session, arguments.lead_id, tenant_id=context.principal.tenant_id
        )
        if lead is None:
            raise ToolError(f"Lead {arguments.lead_id} not found")
        return {"lead_id": lead.id, "lead": _lead_to_dict(lead)}


register_tool(CreateLeadTool())
register_tool(UpdateLeadTool())
register_tool(GetLeadTool())
