"""Tool registry auto-populated on import."""

from .base import TOOL_REGISTRY, Tool, ToolContext, register_tool

# Import side-effect: registers all tools.
from . import knowledge  # noqa: F401
from . import crm  # noqa: F401
from . import scoring  # noqa: F401
from . import calendar  # noqa: F401
from . import memory  # noqa: F401

__all__ = ["TOOL_REGISTRY", "Tool", "ToolContext", "register_tool"]
