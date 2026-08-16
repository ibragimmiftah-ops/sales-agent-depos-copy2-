"""Tool registry auto-populated on import."""

# Import side-effect: registers all tools.
from . import (
    calendar,  # noqa: F401
    crm,  # noqa: F401
    knowledge,  # noqa: F401
    memory,  # noqa: F401
    scoring,  # noqa: F401
)
from .base import TOOL_REGISTRY, Tool, ToolContext, register_tool

__all__ = ["TOOL_REGISTRY", "Tool", "ToolContext", "register_tool"]
