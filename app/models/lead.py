"""Lead model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .mixins import TenantMixin

if TYPE_CHECKING:
    from .conversation import Conversation
    from .event import LeadEvent
    from .meeting import Meeting


def _gen_lead_id() -> str:
    return f"lead_{uuid.uuid4().hex[:12]}"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    ENGAGED = "engaged"
    QUALIFICATION = "qualification"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    MEETING_PROPOSED = "meeting_proposed"
    MEETING_BOOKED = "meeting_booked"
    NOT_INTERESTED = "not_interested"
    CLOSED = "closed"


class LeadQuality(str, enum.Enum):
    LOW = "low"
    POTENTIAL = "potential"
    QUALIFIED = "qualified"


class Lead(TenantMixin, Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_lead_id)
    conversation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=True
    )

    # Identity / contact
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)

    # Firmographics
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    company_size: Mapped[str | None] = mapped_column(String, nullable=True)

    # Qualification
    business_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_solution: Mapped[str | None] = mapped_column(String, nullable=True)
    current_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_software: Mapped[str | None] = mapped_column(String, nullable=True)
    channels: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    monthly_leads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_customer_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_range: Mapped[str | None] = mapped_column(String, nullable=True)
    deadline: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_maker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    urgency: Mapped[str | None] = mapped_column(String, nullable=True)
    additional_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scoring / funnel
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_quality: Mapped[LeadQuality | None] = mapped_column(String, nullable=True)
    status: Mapped[LeadStatus] = mapped_column(String, default=LeadStatus.NEW.value)
    next_best_action: Mapped[str | None] = mapped_column(String, nullable=True)

    # Meeting
    meeting_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    conversation: Mapped[Conversation] = relationship(
        foreign_keys="[Lead.conversation_id]",
        uselist=False,
    )
    events: Mapped[list[LeadEvent]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    meetings: Mapped[list[Meeting]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
