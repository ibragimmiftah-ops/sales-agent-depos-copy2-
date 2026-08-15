"""Meeting model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .lead import Lead


def _gen_meeting_id() -> str:
    return f"meeting_{uuid.uuid4().hex[:12]}"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=_gen_meeting_id
    )
    lead_id: Mapped[str] = mapped_column(
        String, ForeignKey("leads.id", ondelete="CASCADE")
    )
    datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    timezone: Mapped[str] = mapped_column(String, default="Europe/Helsinki")
    status: Mapped[str] = mapped_column(String, default="scheduled")  # scheduled | cancelled | completed
    meeting_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    lead: Mapped["Lead"] = relationship(back_populates="meetings")
