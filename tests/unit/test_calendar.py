"""Tests for the tenant-aware calendar service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CalendarError
from app.models import Tenant
from app.services.calendar import CalendarService
from app.services.crm import CRMService


@pytest.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    t = Tenant(id="tenant_cal", name="Calendar Test", is_public=False)
    db_session.add(t)
    await db_session.commit()
    return t


@pytest.fixture
def calendar() -> CalendarService:
    return CalendarService()


@pytest.mark.asyncio
async def test_generate_slots_in_range(
    db_session: AsyncSession, calendar: CalendarService, tenant: Tenant
):
    slots = await calendar.get_available_slots(
        db_session,
        tenant_id=tenant.id,
        timezone="Europe/Helsinki",
        date_from="2026-08-18",
        date_to="2026-08-18",
        duration_minutes=30,
    )
    assert len(slots) > 0
    assert all("2026-08-18" in s for s in slots)


@pytest.mark.asyncio
async def test_book_and_prevent_double_booking(
    db_session: AsyncSession, calendar: CalendarService, tenant: Tenant
):
    lead = await CRMService.create_lead(
        db_session, {"name": "Alex", "email": "alex@example.com"},
        tenant_id=tenant.id,
    )
    await db_session.commit()

    slot = "2026-08-18T12:00:00+03:00"
    meeting = await calendar.book_meeting(
        db_session,
        tenant_id=tenant.id,
        lead_id=lead.id,
        datetime_str=slot,
        duration_minutes=30,
        name="Alex",
        email="alex@example.com",
        timezone="Europe/Helsinki",
    )
    assert meeting.lead_id == lead.id
    assert meeting.datetime.isoformat() == slot

    with pytest.raises(CalendarError):
        await calendar.book_meeting(
            db_session,
            tenant_id=tenant.id,
            lead_id=lead.id,
            datetime_str=slot,
            duration_minutes=30,
            name="Alex",
            email="alex@example.com",
            timezone="Europe/Helsinki",
        )


@pytest.mark.asyncio
async def test_invalid_timezone_raises(
    db_session: AsyncSession, calendar: CalendarService, tenant: Tenant
):
    with pytest.raises(CalendarError):
        await calendar.get_available_slots(
            db_session,
            tenant_id=tenant.id,
            timezone="Mars/Phobos",
        date_from="2026-08-18",
        date_to="2026-08-18",
            duration_minutes=30,
        )


@pytest.mark.asyncio
async def test_cannot_book_past_slot(
    db_session: AsyncSession, calendar: CalendarService, tenant: Tenant
):
    lead = await CRMService.create_lead(
        db_session, {"name": "Alex"}, tenant_id=tenant.id
    )
    await db_session.commit()
    with pytest.raises(CalendarError):
        await calendar.book_meeting(
            db_session,
            tenant_id=tenant.id,
            lead_id=lead.id,
            datetime_str="2020-01-01T12:00:00+03:00",
            duration_minutes=30,
            name="Alex",
            email="",
            timezone="Europe/Helsinki",
        )
