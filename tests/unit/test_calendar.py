"""Tests for the calendar service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CalendarError
from app.services.calendar import CalendarService
from app.services.crm import CRMService


@pytest.fixture
def calendar() -> CalendarService:
    return CalendarService()


@pytest.mark.asyncio
async def test_generate_slots_in_range(db_session: AsyncSession, calendar: CalendarService):
    slots = await calendar.get_available_slots(
        db_session,
        timezone="Europe/Helsinki",
        date_from="2026-08-17",
        date_to="2026-08-17",
        duration_minutes=30,
    )
    assert len(slots) > 0
    assert all("2026-08-17" in s for s in slots)


@pytest.mark.asyncio
async def test_book_and_prevent_double_booking(
    db_session: AsyncSession, calendar: CalendarService
):
    lead = await CRMService.create_lead(db_session, {"name": "Alex", "email": "alex@example.com"})
    await db_session.commit()

    slot = "2026-08-17T12:00:00+03:00"
    meeting = await calendar.book_meeting(
        db_session,
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
            lead_id=lead.id,
            datetime_str=slot,
            duration_minutes=30,
            name="Alex",
            email="alex@example.com",
            timezone="Europe/Helsinki",
        )


@pytest.mark.asyncio
async def test_invalid_timezone_raises(db_session: AsyncSession, calendar: CalendarService):
    with pytest.raises(CalendarError):
        await calendar.get_available_slots(
            db_session,
            timezone="Mars/Phobos",
            date_from="2026-08-17",
            date_to="2026-08-17",
            duration_minutes=30,
        )
