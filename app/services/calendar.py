"""Mock calendar service for meeting slots and booking."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import CalendarError
from app.core.logging import get_logger
from app.models import Lead, LeadStatus, Meeting
from app.services.crm import CRMService

logger = get_logger(__name__)


class CalendarService:
    """Generates deterministic availability and books meetings."""

    def __init__(self) -> None:
        self.duration = settings.SLOT_DURATION_MINUTES
        self.start_hour = settings.BUSINESS_HOURS_START
        self.end_hour = settings.BUSINESS_HOURS_END

    async def get_available_slots(
        self,
        session: AsyncSession,
        *,
        timezone: str,
        date_from: str,
        date_to: str,
        duration_minutes: int,
        exclude_lead_id: str | None = None,
    ) -> list[str]:
        """Return ISO 8601 slot strings between date_from and date_to."""
        try:
            tz = ZoneInfo(timezone)
        except Exception as exc:
            raise CalendarError(f"Invalid timezone: {timezone}") from exc

        try:
            start_date = date.fromisoformat(date_from)
            end_date = date.fromisoformat(date_to)
        except ValueError as exc:
            raise CalendarError("date_from/date_to must be YYYY-MM-DD") from exc

        if end_date < start_date:
            raise CalendarError("date_to cannot be earlier than date_from")

        # Load existing meetings in range.
        range_start = datetime.combine(start_date, time.min, tzinfo=tz)
        range_end = datetime.combine(end_date, time.max, tzinfo=tz)
        stmt = select(Meeting).where(
            Meeting.datetime >= range_start,
            Meeting.datetime <= range_end,
            Meeting.status == "scheduled",
        )
        if exclude_lead_id:
            stmt = stmt.where(Meeting.lead_id != exclude_lead_id)
        result = await session.execute(stmt)
        busy_starts = {m.datetime for m in result.scalars().all()}

        slots: list[str] = []
        current = start_date
        while current <= end_date:
            for hour in range(self.start_hour, self.end_hour):
                for minute in (0, 30):
                    slot_local = datetime.combine(
                        current, time(hour, minute), tzinfo=tz
                    )
                    slot_utc = slot_local.astimezone(ZoneInfo("UTC"))
                    if slot_utc in busy_starts:
                        continue
                    slot_end = slot_local + timedelta(minutes=duration_minutes)
                    if slot_end.hour > self.end_hour or (
                        slot_end.hour == self.end_hour and slot_end.minute > 0
                    ):
                        continue
                    slots.append(slot_local.isoformat())
            current += timedelta(days=1)

        logger.info(
            "calendar_slots_generated",
            timezone=timezone,
            date_from=date_from,
            date_to=date_to,
            slots_count=len(slots),
        )
        return slots[:10]  # limit to avoid overwhelming UI

    async def book_meeting(
        self,
        session: AsyncSession,
        *,
        lead_id: str,
        datetime_str: str,
        duration_minutes: int,
        name: str,
        email: str,
        timezone: str | None = None,
    ) -> Meeting:
        """Book a meeting if the slot is still available."""
        tz_name = timezone or settings.DEFAULT_TIMEZONE
        try:
            tz = ZoneInfo(tz_name)
            slot = datetime.fromisoformat(datetime_str)
            if slot.tzinfo is None:
                slot = slot.replace(tzinfo=tz)
            else:
                slot = slot.astimezone(tz)
        except Exception as exc:
            raise CalendarError(f"Invalid datetime or timezone: {exc}") from exc

        # Check availability.
        existing = await session.execute(
            select(Meeting).where(
                Meeting.datetime == slot,
                Meeting.status == "scheduled",
            )
        )
        if existing.scalar_one_or_none():
            raise CalendarError("Slot already booked")

        meeting = Meeting(
            lead_id=lead_id,
            datetime=slot,
            duration_minutes=duration_minutes,
            timezone=tz_name,
            status="scheduled",
            meeting_url=f"https://meet.novaflow.ai/{lead_id}",
        )
        session.add(meeting)

        await CRMService.update_lead(
            session,
            lead_id,
            {"meeting_datetime": slot},
        )
        await CRMService.update_lead_status(
            session,
            lead_id,
            LeadStatus.MEETING_BOOKED,
            reason="Meeting booked via calendar tool",
        )
        await CRMService.append_event(
            session,
            lead_id,
            "meeting_booked",
            {
                "meeting_id": meeting.id,
                "datetime": meeting.datetime.isoformat(),
                "duration_minutes": duration_minutes,
            },
        )
        await session.flush()
        logger.info(
            "meeting_booked",
            lead_id=lead_id,
            meeting_id=meeting.id,
            datetime=meeting.datetime.isoformat(),
        )
        return meeting
