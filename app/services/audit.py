"""Persistent audit logging for tool calls and agent runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ToolCall

logger = get_logger(__name__)


def _redact(value: Any) -> Any:
    """Remove sensitive fields from logged arguments/results."""
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k in {"email", "phone", "api_key", "password"} else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class AuditService:
    """Persist tool-call records for observability and compliance."""

    @staticmethod
    async def record_tool_call(
        session: AsyncSession,
        *,
        tenant_id: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        latency_ms: int | None = None,
        run_id: str | None = None,
        request_id: str | None = None,
        conversation_id: str | None = None,
        lead_id: str | None = None,
    ) -> ToolCall:
        record = ToolCall(
            tenant_id=tenant_id,
            tool=tool,
            arguments=_redact(arguments),
            result=_redact(result),
            error=error,
            latency_ms=latency_ms,
            status="failure" if error else "success",
            run_id=run_id,
            request_id=request_id,
            conversation_id=conversation_id,
            lead_id=lead_id,
        )
        session.add(record)
        await session.flush()
        logger.info(
            "tool_call_audited",
            tool_call_id=record.id,
            tool=tool,
            run_id=run_id,
            status=record.status,
        )
        return record
