"""Lead event audit model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .mixins import TenantMixin

if TYPE_CHECKING:
    from .lead import Lead


def _gen_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:12]}"


class LeadEvent(TenantMixin, Base):
    __tablename__ = "lead_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_event_id)
    lead_id: Mapped[str] = mapped_column(
        String, ForeignKey("leads.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    lead: Mapped[Lead] = relationship(back_populates="events")
