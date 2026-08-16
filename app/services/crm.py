"""Tenant-aware CRM service with typed, allowlisted update commands."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CRMError
from app.core.logging import get_logger
from app.models import Conversation, Lead, LeadEvent, LeadStatus

logger = get_logger(__name__)


# Fields that may never be updated through generic or LLM-driven paths.
_IMMUTABLE_FIELDS: set[str] = {
    "id",
    "tenant_id",
    "conversation_id",
    "lead_score",
    "lead_quality",
    "status",
    "created_at",
    "updated_at",
}

# Fields that an operator may update through the API.
OPERATOR_UPDATABLE_FIELDS: set[str] = {
    "name",
    "company",
    "email",
    "phone",
    "industry",
    "company_size",
    "business_problem",
    "desired_solution",
    "current_process",
    "current_software",
    "channels",
    "monthly_leads",
    "monthly_customer_requests",
    "budget_range",
    "deadline",
    "decision_maker",
    "urgency",
    "additional_notes",
    "next_best_action",
}

# Fields that the agent may update via memory_updates / tools.
AGENT_UPDATABLE_FIELDS: set[str] = {
    "name",
    "company",
    "email",
    "phone",
    "industry",
    "company_size",
    "business_problem",
    "desired_solution",
    "current_process",
    "current_software",
    "channels",
    "monthly_leads",
    "monthly_customer_requests",
    "budget_range",
    "deadline",
    "decision_maker",
    "urgency",
    "additional_notes",
}


def _serialize_event_value(value: Any) -> Any:
    """Make a value JSON-serializable for event payloads."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _validate_update_fields(fields: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Return only allowed fields, raising on immutable/internal fields.

    If an immutable field is explicitly listed in ``allowed`` it may be updated
    (used for system-controlled updates such as lead_score).
    """
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if key in _IMMUTABLE_FIELDS and key not in allowed:
            raise CRMError(f"Field '{key}' cannot be modified", details={"field": key})
        if key not in allowed:
            raise CRMError(f"Unknown or unauthorized field: {key}", details={"field": key})
        cleaned[key] = value
    return cleaned


class CRMService:
    """Service layer over the leads/events tables.

    All queries are filtered by tenant_id. All mutations are appended to
    lead_events for audit and dashboard timelines.
    """

    @staticmethod
    async def get_lead(
        session: AsyncSession, lead_id: str, *, tenant_id: str
    ) -> Lead | None:
        result = await session.execute(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_lead_by_email_or_phone(
        session: AsyncSession,
        *,
        tenant_id: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> Lead | None:
        if not email and not phone:
            return None
        stmt = select(Lead).where(Lead.tenant_id == tenant_id)
        if email and phone:
            stmt = stmt.where((Lead.email == email) | (Lead.phone == phone))
        elif email:
            stmt = stmt.where(Lead.email == email)
        else:
            stmt = stmt.where(Lead.phone == phone)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_or_create_conversation_lead(
        cls,
        session: AsyncSession,
        conversation_id: str,
        *,
        tenant_id: str,
    ) -> Lead:
        """Return existing lead for conversation or create a fresh one."""
        conv_result = await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id,
            )
        )
        conversation = conv_result.scalar_one_or_none()

        if conversation is None:
            conversation = Conversation(id=conversation_id, tenant_id=tenant_id)
            session.add(conversation)
            await session.flush()
            logger.info(
                "conversation_created",
                conversation_id=conversation_id,
                tenant_id=tenant_id,
            )

        if conversation.lead_id:
            lead = await cls.get_lead(
                session, conversation.lead_id, tenant_id=tenant_id
            )
            if lead:
                return lead

        lead = Lead(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            status=LeadStatus.NEW,
        )
        session.add(lead)
        await session.flush()
        conversation.lead_id = lead.id
        await session.flush()

        await cls.append_event(
            session,
            lead.id,
            tenant_id=tenant_id,
            event_type="lead_created",
            payload={"conversation_id": conversation_id},
            note="Lead created from conversation",
        )
        return lead

    @classmethod
    async def create_lead(
        cls,
        session: AsyncSession,
        data: dict[str, Any],
        *,
        tenant_id: str,
        conversation_id: str | None = None,
    ) -> Lead:
        """Create a lead, de-duplicating by email/phone within the tenant."""
        allowed = _validate_update_fields(data, OPERATOR_UPDATABLE_FIELDS)
        email = allowed.get("email")
        phone = allowed.get("phone")
        existing = await cls.get_lead_by_email_or_phone(
            session, tenant_id=tenant_id, email=email, phone=phone
        )
        if existing:
            logger.info(
                "lead_duplicate_detected",
                existing_lead_id=existing.id,
                email=email,
                phone=phone,
                tenant_id=tenant_id,
            )
            return await cls.update_lead(
                session, existing.id, tenant_id=tenant_id, fields=allowed
            )

        lead = Lead(**allowed, tenant_id=tenant_id)
        if conversation_id:
            lead.conversation_id = conversation_id
        if lead.status is None:
            lead.status = LeadStatus.NEW
        session.add(lead)
        await session.flush()

        await cls.append_event(
            session,
            lead.id,
            tenant_id=tenant_id,
            event_type="lead_created",
            payload={"source": "tool_create_lead", "fields": list(allowed.keys())},
        )
        return lead

    @classmethod
    async def update_lead(
        cls,
        session: AsyncSession,
        lead_id: str,
        *,
        tenant_id: str,
        fields: dict[str, Any],
        allowed_fields: set[str] | None = None,
    ) -> Lead:
        allowed = allowed_fields or OPERATOR_UPDATABLE_FIELDS | AGENT_UPDATABLE_FIELDS
        cleaned = _validate_update_fields(fields, allowed)

        lead = await cls.get_lead(session, lead_id, tenant_id=tenant_id)
        if lead is None:
            raise CRMError(f"Lead {lead_id} not found")

        changed: dict[str, Any] = {}
        for key, value in cleaned.items():
            old = getattr(lead, key)
            if old != value:
                setattr(lead, key, value)
                changed[key] = {
                    "old": _serialize_event_value(old),
                    "new": _serialize_event_value(value),
                }

        if changed:
            await cls.append_event(
                session,
                lead_id,
                tenant_id=tenant_id,
                event_type="field_updated",
                payload=changed,
            )
            logger.info(
                "lead_updated",
                lead_id=lead_id,
                tenant_id=tenant_id,
                changed_fields=list(changed.keys()),
            )

        return lead

    @classmethod
    async def update_lead_status(
        cls,
        session: AsyncSession,
        lead_id: str,
        *,
        tenant_id: str,
        status: LeadStatus,
        reason: str | None = None,
    ) -> Lead:
        lead = await cls.get_lead(session, lead_id, tenant_id=tenant_id)
        if lead is None:
            raise CRMError(f"Lead {lead_id} not found")
        if lead.status == status:
            return lead
        lead.status = status
        await cls.append_event(
            session,
            lead_id,
            tenant_id=tenant_id,
            event_type="stage_changed",
            payload={"status": status.value},
            note=reason,
        )
        return lead

    @staticmethod
    async def append_event(
        session: AsyncSession,
        lead_id: str,
        *,
        tenant_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        note: str | None = None,
    ) -> LeadEvent:
        event = LeadEvent(
            lead_id=lead_id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload or {},
            note=note,
        )
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def list_leads(
        session: AsyncSession, *, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> list[Lead]:
        result = await session.execute(
            select(Lead)
            .where(Lead.tenant_id == tenant_id)
            .order_by(Lead.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
