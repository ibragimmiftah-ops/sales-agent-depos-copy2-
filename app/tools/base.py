"""Tool registry and base class for agent tools."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ToolError
from app.core.logging import get_logger
from app.core.security import Principal
from app.rag.retrieval import KnowledgeRetriever
from app.services.audit import AuditService
from app.services.calendar import CalendarService

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ToolContext:
    """Immutable request-scoped dependencies passed to every tool execution."""

    session: AsyncSession
    retriever: KnowledgeRetriever
    calendar_service: CalendarService
    principal: Principal
    run_id: str
    request_id: str | None = None
    conversation_id: str | None = None
    lead_id: str | None = None


class Tool[T](ABC):
    """Abstract agent tool with Pydantic input/output schemas."""

    name: str
    description: str
    input_schema: type[T]
    output_schema: type[BaseModel] | None = None

    @abstractmethod
    async def execute(self, context: ToolContext, arguments: T) -> dict[str, Any]:
        """Run the tool and return a JSON-serializable result dict."""
        ...


class ToolRegistry:
    """Central registry and executor for agent tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already registered")
        self._tools[tool.name] = tool
        logger.debug("tool_registered", tool=tool.name)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    async def execute(
        self,
        context: ToolContext,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool: {name}")

        try:
            validated = tool.input_schema.model_validate(arguments)
        except Exception as exc:
            raise ToolError(f"Invalid arguments for {name}: {exc}") from exc

        start = time.perf_counter()
        error: str | None = None
        result: dict[str, Any] = {}
        try:
            result = await tool.execute(context, validated)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "tool_executed",
                tool=name,
                run_id=context.run_id,
                latency_ms=latency_ms,
                success=True,
            )
            result = {"success": True, **result}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            error = str(exc)
            logger.error(
                "tool_execution_failed",
                tool=name,
                run_id=context.run_id,
                latency_ms=latency_ms,
                error=error,
            )
            result = {"success": False, "error": error}

        await AuditService.record_tool_call(
            context.session,
            tenant_id=context.principal.tenant_id,
            tool=name,
            arguments=arguments,
            result=result if not error else None,
            error=error,
            latency_ms=latency_ms,
            run_id=context.run_id,
            request_id=context.request_id,
            conversation_id=context.conversation_id,
            lead_id=context.lead_id,
        )
        return result


TOOL_REGISTRY = ToolRegistry()


def register_tool(tool: Tool) -> Tool:
    """Decorator / helper to register a tool instance."""
    TOOL_REGISTRY.register(tool)
    return tool
