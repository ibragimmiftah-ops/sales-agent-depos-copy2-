"""Leads, events, and conversations endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LeadUpdateRequest
from app.core.database import get_db
from app.core.exceptions import ServiceError
from app.models import Lead, LeadEvent
from app.services.crm import CRMService

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=list[dict[str, Any]])
async def list_leads(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    leads = await CRMService.list_leads(db, limit=limit, offset=offset)
    return [_lead_to_dict(l) for l in leads]


@router.get("/{lead_id}", response_model=dict[str, Any])
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await CRMService.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _lead_to_dict(lead)


@router.patch("/{lead_id}", response_model=dict[str, Any])
async def update_lead(
    lead_id: str,
    request: LeadUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        lead = await CRMService.update_lead(db, lead_id, request.fields)
        await db.commit()
    except ServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _lead_to_dict(lead)


@router.get("/{lead_id}/events", response_model=list[dict[str, Any]])
async def get_lead_events(lead_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LeadEvent)
        .where(LeadEvent.lead_id == lead_id)
        .order_by(LeadEvent.created_at.desc())
    )
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "payload": e.payload,
            "note": e.note,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]


def _lead_to_dict(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
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


