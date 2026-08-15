"""Application-specific exceptions."""


class ServiceError(Exception):
    """Base service error."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CRMError(ServiceError):
    """CRM operation failed."""


class CalendarError(ServiceError):
    """Calendar operation failed."""


class RAGError(ServiceError):
    """RAG retrieval failed."""


class LLMError(ServiceError):
    """LLM call failed."""


class ToolError(ServiceError):
    """Tool execution failed."""
