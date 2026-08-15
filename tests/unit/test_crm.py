"""Tests for the mock CRM service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LeadStatus
from app.services.crm import CRMService


@pytest.mark.asyncio
async def test_create_lead_and_audit_event(db_session: AsyncSession):
    lead = await CRMService.create_lead(
        db_session, {"company": "Dental Pro", "business_problem": "slow leads"}
    )
    assert lead.id.startswith("lead_")
    assert lead.company == "Dental Pro"

    await db_session.refresh(lead, ["events"])
    assert any(e.event_type == "lead_created" for e in lead.events)


@pytest.mark.asyncio
async def test_update_lead_emits_field_updated_event(db_session: AsyncSession):
    lead = await CRMService.create_lead(db_session, {"company": "X"})
    await CRMService.update_lead(
        db_session, lead.id, {"monthly_leads": 500, "current_software": "HubSpot"}
    )
    await db_session.commit()

    refreshed = await CRMService.get_lead(db_session, lead.id)
    assert refreshed.monthly_leads == 500
    assert refreshed.current_software == "HubSpot"


@pytest.mark.asyncio
async def test_duplicate_lead_by_email_updates_existing(db_session: AsyncSession):
    first = await CRMService.create_lead(
        db_session, {"email": "alex@example.com", "name": "Alex"}
    )
    second = await CRMService.create_lead(
        db_session, {"email": "alex@example.com", "company": "Dental Pro"}
    )
    assert first.id == second.id
    assert second.company == "Dental Pro"
