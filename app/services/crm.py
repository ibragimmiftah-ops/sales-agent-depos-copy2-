"""Mock CRM service with audit trail."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CRMError
from app.core.logging import get_logger
from app.models import Conversation, Lead, LeadEvent, LeadStatus

logger = get_logger(__name__)


class CRMService:
    """Service layer over the leads/events tables.

    All mutations are appended to lead_events for audit and dashboard timelines.
    """

    @staticmethod
    async def get_lead(session: AsyncSession, lead_id: str) -> Lead | None:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_lead_by_email_or_phone(
        session: AsyncSession, *, email: str | None = None, phone: str | None = None
    ) -> Lead | None:
        if not email and not phone:
            return None
        stmt = select(Lead)
        if email and phone:
            stmt = stmt.where((Lead.email == email) | (Lead.phone == phone))
        elif email:
            stmt = stmt.where(Lead.email == email)
        else:
            stmt = stmt.where(Lead.phone == phone)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_conversation_lead(
        session: AsyncSession, conversation_id: str
    ) -> Lead:
        """Return existing lead for conversation or create a fresh one."""
        conv_result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()

        if conversation is None:
            conversation = Conversation(id=conversation_id)
            session.add(conversation)
            await session.flush()
            logger.info("conversation_created", conversation_id=conversation_id)

        if conversation.lead_id:
            lead = await CRMService.get_lead(session, conversation.lead_id)
            if lead:
                return lead

        lead = Lead(conversation_id=conversation_id, status=LeadStatus.NEW)
        session.add(lead)
        await session.flush()
        conversation.lead_id = lead.id
        await session.flush()

        await CRMService.append_event(
            session,
            lead.id,
            "lead_created",
            {"conversation_id": conversation_id},
            note="Lead created from conversation",
        )
        return lead

    @classmethod
    async def create_lead(
        cls,
        session: AsyncSession,
        data: dict[str, Any],
        *,
        conversation_id: str | None = None,
    ) -> Lead:
        """Create a lead, de-duplicating by email/phone when possible."""
        email = data.get("email")
        phone = data.get("phone")
        existing = await cls.get_lead_by_email_or_phone(
            session, email=email, phone=phone
        )
        if existing:
            logger.info(
                "lead_duplicate_detected",
                existing_lead_id=existing.id,
                email=email,
                phone=phone,
            )
            return await cls.update_lead(session, existing.id, data)

        lead = Lead(**data)
        if conversation_id:
            lead.conversation_id = conversation_id
        if lead.status is None:
            lead.status = LeadStatus.NEW
        session.add(lead)
        await session.flush()

        if conversation_id:
            await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            # Linking handled in get_or_create_conversation_lead usually.

        await cls.append_event(
            session,
            lead.id,
            "lead_created",
            {"source": "tool_create_lead", "fields": list(data.keys())},
        )
        return lead

    @classmethod
    async def update_lead(
        cls,
        session: AsyncSession,
        lead_id: str,
        fields: dict[str, Any],
    ) -> Lead:
        lead = await cls.get_lead(session, lead_id)
        if lead is None:
            raise CRMError(f"Lead {lead_id} not found")

        changed: dict[str, Any] = {}
        for key, value in fields.items():
            if not hasattr(Lead, key):
                continue
            old = getattr(lead, key)
            if old != value:
                setattr(lead, key, value)
                changed[key] = {"old": old, "new": value}

        if changed:
            await cls.append_event(
                session,
                lead_id,
                "field_updated",
                changed,
            )
            logger.info("lead_updated", lead_id=lead_id, changed_fields=list(changed.keys()))

        return lead

    @classmethod
    async def update_lead_status(
        cls,
        session: AsyncSession,
        lead_id: str,
        status: LeadStatus,
        *,
        reason: str | None = None,
    ) -> Lead:
        lead = await cls.update_lead(session, lead_id, {"status": status.value})
        await cls.append_event(
            session,
            lead_id,
            "stage_changed",
            {"status": status.value},
            note=reason,
        )
        return lead

    @staticmethod
    async def append_event(
        session: AsyncSession,
        lead_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        note: str | None = None,
    ) -> LeadEvent:
        event = LeadEvent(
            lead_id=lead_id,
            event_type=event_type,
            payload=payload or {},
            note=note,
        )
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def list_leads(session: AsyncSession, *, limit: int = 100, offset: int = 0):
        result = await session.execute(
            select(Lead).order_by(Lead.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
