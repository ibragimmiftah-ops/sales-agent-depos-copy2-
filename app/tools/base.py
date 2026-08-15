"""Tool registry and base class for agent tools."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Type

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ToolError
from app.core.logging import get_logger
from app.rag.retrieval import KnowledgeRetriever
from app.services.calendar import CalendarService

logger = get_logger(__name__)


@dataclass
class ToolContext:
    """Dependencies passed to every tool execution."""

    session: AsyncSession
    retriever: KnowledgeRetriever
    calendar_service: CalendarService


class Tool(ABC):
    """Abstract agent tool with Pydantic input/output schemas."""

    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel] | None = None

    @abstractmethod
    async def execute(self, context: ToolContext, arguments: BaseModel) -> dict[str, Any]:
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
        try:
            result = await tool.execute(context, validated)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "tool_executed",
                tool=name,
                latency_ms=latency_ms,
                success=True,
            )
            return {"success": True, **result}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "tool_execution_failed",
                tool=name,
                latency_ms=latency_ms,
                error=str(exc),
            )
            return {"success": False, "error": str(exc)}


TOOL_REGISTRY = ToolRegistry()


def register_tool(tool: Tool) -> Tool:
    """Decorator / helper to register a tool instance."""
    TOOL_REGISTRY.register(tool)
    return tool
