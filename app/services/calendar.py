"""Tenant-aware calendar service with atomic overlap checks and offered-slot tokens."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import CalendarError
from app.core.logging import get_logger
from app.models import Meeting
from app.services.crm import CRMService

logger = get_logger(__name__)

OFFERED_SLOT_TTL_MINUTES = 10


def _slot_to_datetime(slot_local: datetime) -> datetime:
    return slot_local.astimezone(ZoneInfo("UTC"))


class CalendarService:
    """Generates deterministic availability and books meetings per tenant."""

    def __init__(self) -> None:
        self.duration = settings.SLOT_DURATION_MINUTES
        self.start_hour = settings.BUSINESS_HOURS_START
        self.end_hour = settings.BUSINESS_HOURS_END

    async def get_available_slots(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
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

        range_start = datetime.combine(start_date, time.min, tzinfo=tz)
        range_end = datetime.combine(end_date, time.max, tzinfo=tz)
        stmt = select(Meeting).where(
            Meeting.tenant_id == tenant_id,
            Meeting.datetime >= range_start,
            Meeting.datetime <= range_end,
            Meeting.status == "scheduled",
        )
        if exclude_lead_id:
            stmt = stmt.where(Meeting.lead_id != exclude_lead_id)
        result = await session.execute(stmt)
        busy_intervals = [
            (m.datetime, m.datetime + timedelta(minutes=m.duration_minutes))
            for m in result.scalars().all()
        ]

        slots: list[str] = []
        current = start_date
        now = datetime.now(ZoneInfo("UTC"))
        while current <= end_date:
            for hour in range(self.start_hour, self.end_hour):
                for minute in (0, 30):
                    slot_local = datetime.combine(
                        current, time(hour, minute), tzinfo=tz
                    )
                    slot_utc = slot_local.astimezone(ZoneInfo("UTC"))
                    if slot_utc <= now:
                        continue
                    slot_end_local = slot_local + timedelta(minutes=duration_minutes)
                    if slot_end_local.hour > self.end_hour or (
                        slot_end_local.hour == self.end_hour
                        and slot_end_local.minute > 0
                    ):
                        continue
                    # Overlap check against existing meetings.
                    overlaps = any(
                        start < slot_end_local and slot_local < end
                        for start, end in busy_intervals
                    )
                    if overlaps:
                        continue
                    slots.append(slot_local.isoformat())
            current += timedelta(days=1)

        logger.info(
            "calendar_slots_generated",
            tenant_id=tenant_id,
            timezone=timezone,
            date_from=date_from,
            date_to=date_to,
            slots_count=len(slots),
        )
        return slots[:10]

    async def offer_slot_token(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        lead_id: str,
        slot: str,
        duration_minutes: int,
    ) -> str:
        """Create a temporary token that authorizes booking a specific slot."""
        try:
            tz_name = settings.DEFAULT_TIMEZONE
            slot_dt = datetime.fromisoformat(slot)
            if slot_dt.tzinfo is None:
                slot_dt = slot_dt.replace(tzinfo=ZoneInfo(tz_name))
        except Exception as exc:
            raise CalendarError(f"Invalid slot: {exc}") from exc

        # Store as a scheduled meeting with a pending status so the slot is reserved.
        pending = Meeting(
            tenant_id=tenant_id,
            lead_id=lead_id,
            datetime=slot_dt,
            duration_minutes=duration_minutes,
            timezone=tz_name,
            status="offered",
            meeting_url=None,
        )
        session.add(pending)
        await session.flush()
        logger.info(
            "slot_offered",
            tenant_id=tenant_id,
            lead_id=lead_id,
            meeting_id=pending.id,
            slot=slot,
        )
        return pending.id

    async def book_meeting(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        lead_id: str,
        datetime_str: str,
        duration_minutes: int,
        name: str,
        email: str,
        timezone: str | None = None,
        offered_meeting_id: str | None = None,
    ) -> Meeting:
        """Book a meeting if the slot is valid and not already taken."""
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

        now = datetime.now(ZoneInfo("UTC"))
        if slot.astimezone(ZoneInfo("UTC")) <= now:
            raise CalendarError("Cannot book a slot in the past")

        # Validate business hours.
        slot_end = slot + timedelta(minutes=duration_minutes)
        if slot.hour < self.start_hour or slot_end.hour > self.end_hour or (
            slot_end.hour == self.end_hour and slot_end.minute > 0
        ):
            raise CalendarError("Slot is outside business hours")

        # If an offered token is provided, validate it matches and is not expired.
        if offered_meeting_id:
            offered_result = await session.execute(
                select(Meeting).where(
                    Meeting.id == offered_meeting_id,
                    Meeting.tenant_id == tenant_id,
                    Meeting.lead_id == lead_id,
                    Meeting.status == "offered",
                )
            )
            offered = offered_result.scalar_one_or_none()
            if offered is None:
                raise CalendarError("Offered slot is invalid or expired")
            if offered.datetime != slot:
                raise CalendarError("Offered slot does not match requested time")
            # Reject offers older than TTL.
            offer_age = datetime.now(ZoneInfo("UTC")) - offered.created_at
            if offer_age > timedelta(minutes=OFFERED_SLOT_TTL_MINUTES):
                offered.status = "cancelled"
                raise CalendarError("Offered slot has expired")

        # Atomic overlap check using pessimistic read. We already hold the
        # transaction; concurrent requests will serialize at commit.
        existing = await session.execute(
            select(Meeting).where(
                Meeting.tenant_id == tenant_id,
                Meeting.datetime == slot,
                Meeting.status.in_(["scheduled"]),
            )
        )
        if existing.scalar_one_or_none():
            raise CalendarError("Slot already booked")

        meeting = Meeting(
            tenant_id=tenant_id,
            lead_id=lead_id,
            datetime=slot,
            duration_minutes=duration_minutes,
            timezone=tz_name,
            status="scheduled",
            meeting_url=f"https://meet.example.com/{lead_id}",
        )
        session.add(meeting)

        # Cancel any prior offered slot for this lead to avoid orphan pending.
        if offered_meeting_id:
            offered_result = await session.execute(
                select(Meeting).where(
                    Meeting.id == offered_meeting_id,
                    Meeting.tenant_id == tenant_id,
                )
            )
            offered = offered_result.scalar_one_or_none()
            if offered and offered.id != meeting.id:
                offered.status = "cancelled"

        await CRMService.update_lead(
            session,
            lead_id,
            tenant_id=tenant_id,
            fields={"meeting_datetime": slot},
            allowed_fields={"meeting_datetime"},
        )
        await CRMService.append_event(
            session,
            lead_id,
            tenant_id=tenant_id,
            event_type="meeting_booked",
            payload={
                "meeting_id": meeting.id,
                "datetime": meeting.datetime.isoformat(),
                "duration_minutes": duration_minutes,
            },
        )
        await session.flush()
        logger.info(
            "meeting_booked",
            tenant_id=tenant_id,
            lead_id=lead_id,
            meeting_id=meeting.id,
            datetime=meeting.datetime.isoformat(),
        )
        return meeting
