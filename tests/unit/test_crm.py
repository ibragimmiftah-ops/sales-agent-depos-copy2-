"""Tests for the tenant-aware CRM service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CRMError
from app.models import LeadStatus, Tenant
from app.services.crm import CRMService


@pytest.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    t = Tenant(id="tenant_crm", name="CRM Test", is_public=False)
    db_session.add(t)
    await db_session.commit()
    return t


@pytest.mark.asyncio
async def test_create_lead_and_audit_event(db_session: AsyncSession, tenant: Tenant):
    lead = await CRMService.create_lead(
        db_session, {"company": "Dental Pro", "business_problem": "slow leads"},
        tenant_id=tenant.id,
    )
    assert lead.id.startswith("lead_")
    assert lead.company == "Dental Pro"
    assert lead.tenant_id == tenant.id

    await db_session.refresh(lead, ["events"])
    assert any(e.event_type == "lead_created" for e in lead.events)


@pytest.mark.asyncio
async def test_update_lead_emits_field_updated_event(
    db_session: AsyncSession, tenant: Tenant
):
    lead = await CRMService.create_lead(
        db_session, {"company": "X"}, tenant_id=tenant.id
    )
    await CRMService.update_lead(
        db_session,
        lead.id,
        tenant_id=tenant.id,
        fields={"monthly_leads": 500, "current_software": "HubSpot"},
    )
    await db_session.commit()

    refreshed = await CRMService.get_lead(db_session, lead.id, tenant_id=tenant.id)
    assert refreshed.monthly_leads == 500
    assert refreshed.current_software == "HubSpot"


@pytest.mark.asyncio
async def test_update_lead_rejects_internal_fields(
    db_session: AsyncSession, tenant: Tenant
):
    lead = await CRMService.create_lead(
        db_session, {"company": "X"}, tenant_id=tenant.id
    )
    with pytest.raises(CRMError):
        await CRMService.update_lead(
            db_session,
            lead.id,
            tenant_id=tenant.id,
            fields={"status": LeadStatus.QUALIFIED.value},
        )


@pytest.mark.asyncio
async def test_duplicate_lead_by_email_updates_existing(
    db_session: AsyncSession, tenant: Tenant
):
    first = await CRMService.create_lead(
        db_session, {"email": "alex@example.com", "name": "Alex"},
        tenant_id=tenant.id,
    )
    second = await CRMService.create_lead(
        db_session, {"email": "alex@example.com", "company": "Dental Pro"},
        tenant_id=tenant.id,
    )
    assert first.id == second.id
    assert second.company == "Dental Pro"


@pytest.mark.asyncio
async def test_cross_tenant_lead_isolation(db_session: AsyncSession):
    t1 = Tenant(id="tenant_t1", name="T1", is_public=False)
    t2 = Tenant(id="tenant_t2", name="T2", is_public=False)
    db_session.add_all([t1, t2])
    await db_session.commit()

    lead = await CRMService.create_lead(
        db_session, {"company": "T1 Co"}, tenant_id=t1.id
    )
    fetched_t2 = await CRMService.get_lead(
        db_session, lead.id, tenant_id=t2.id
    )
    assert fetched_t2 is None
