"""Long-term memory: structured lead profile persisted in PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.crm import CRMService


class LongTermMemory:
    """Thin wrapper around the CRM lead record for agent memory operations."""

    @staticmethod
    async def apply_updates(
        session: AsyncSession,
        lead_id: str,
        *,
        tenant_id: str,
        fields: dict[str, Any],
    ) -> None:
        """Persist important facts about the lead."""
        await CRMService.update_lead(
            session, lead_id, tenant_id=tenant_id, fields=fields
        )

    @staticmethod
    async def get_profile(
        session: AsyncSession, lead_id: str, *, tenant_id: str
    ) -> dict[str, Any]:
        """Return non-null lead fields as a profile dict."""
        from app.memory.long_term import collect_collected_fields

        lead = await CRMService.get_lead(session, lead_id, tenant_id=tenant_id)
        if lead is None:
            return {}
        return collect_collected_fields(lead)


def collect_collected_fields(lead) -> dict[str, Any]:
    """Extract populated lead fields for dashboard and prompts."""
    fields: dict[str, Any] = {}
    for column in lead.__table__.columns:
        value = getattr(lead, column.name)
        if value not in (None, "", []):
            fields[column.name] = value
    return fields
