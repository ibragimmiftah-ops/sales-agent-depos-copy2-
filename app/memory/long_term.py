"""Long-term memory: structured lead profile persisted in PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead
from app.services.crm import CRMService


class LongTermMemory:
    """Thin wrapper around the CRM lead record for agent memory operations."""

    @staticmethod
    async def apply_updates(
        session: AsyncSession, lead_id: str, fields: dict[str, Any]
    ) -> Lead:
        """Persist important facts about the lead."""
        return await CRMService.update_lead(session, lead_id, fields)

    @staticmethod
    async def get_profile(session: AsyncSession, lead_id: str) -> dict[str, Any]:
        """Return non-null lead fields as a profile dict."""
        lead = await CRMService.get_lead(session, lead_id)
        if lead is None:
            return {}
        return collect_collected_fields(lead)


def collect_collected_fields(lead: Lead) -> dict[str, Any]:
    """Extract populated lead fields for dashboard and prompts."""
    fields: dict[str, Any] = {}
    for column in Lead.__table__.columns:
        value = getattr(lead, column.name)
        if value not in (None, "", []):
            fields[column.name] = value
    return fields
