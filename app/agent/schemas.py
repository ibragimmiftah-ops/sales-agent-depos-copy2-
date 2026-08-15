"""Pydantic schemas for the agent's structured decisions and public state."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

INTENTS = [
    "greeting",
    "service_question",
    "pricing_question",
    "case_study_question",
    "technical_question",
    "new_lead",
    "qualification_answer",
    "meeting_request",
    "meeting_selection",
    "contact_information",
    "objection",
    "not_interested",
    "other",
]

STAGES = [
    "new",
    "engaged",
    "qualification",
    "qualified",
    "unqualified",
    "meeting_proposed",
    "meeting_booked",
    "not_interested",
    "closed",
]

NEXT_BEST_ACTIONS = [
    "answer_question",
    "search_knowledge_base",
    "ask_business_problem",
    "ask_channel",
    "ask_volume",
    "ask_current_software",
    "ask_budget",
    "ask_deadline",
    "ask_authority",
    "request_contact",
    "create_lead",
    "update_lead",
    "calculate_lead_score",
    "offer_meeting",
    "get_available_slots",
    "book_meeting",
    "continue_conversation",
    "end_conversation",
]

TOOLS = [
    "search_knowledge_base",
    "create_lead",
    "update_lead",
    "get_lead",
    "calculate_lead_score",
    "get_available_slots",
    "book_meeting",
    "save_memory",
]


class AgentDecision(BaseModel):
    """Structured decision returned by the LLM for every user message."""

    intent: Literal[tuple(INTENTS)] = Field(..., description="Detected user intent")
    stage: Literal[tuple(STAGES)] = Field(..., description="Target lead stage")
    needs_rag: bool = Field(
        default=False,
        description="Whether the response requires knowledge-base lookup",
    )
    rag_query: str | None = Field(
        default=None,
        description="Cleaned query for RAG if needs_rag is true",
    )
    rag_category: str | None = Field(
        default=None,
        description="Optional metadata category filter for RAG",
    )
    tool: Literal[tuple(TOOLS)] | None = Field(
        default=None,
        description="Tool to call if an external action is required",
    )
    tool_arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the selected tool",
    )
    memory_updates: dict[str, Any] = Field(
        default_factory=dict,
        description="Long-term lead fields to update from this message",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Lead fields still missing, ordered by priority",
    )
    lead_score_required: bool = Field(
        default=False,
        description="Whether the lead score should be recalculated",
    )
    next_best_action: Literal[tuple(NEXT_BEST_ACTIONS)] = Field(
        ...,
        description="Internal next step for observability",
    )
    should_offer_meeting: bool = Field(
        default=False,
        description="Whether the lead is ready for a meeting proposal",
    )
    response: str = Field(
        ...,
        description="User-facing reply text in the same language as the user",
    )


class AgentState(BaseModel):
    """Public state returned by POST /chat for the demo dashboard."""

    conversation_id: str
    lead_id: str | None
    intent: str | None
    stage: str
    lead_score: int | None
    lead_quality: str | None
    next_best_action: str | None
    missing_fields: list[str]
    collected_fields: dict[str, Any]
    last_tool_calls: list[dict[str, Any]]
    response: str

    model_config = ConfigDict(from_attributes=True)


class ToolCallRecord(BaseModel):
    """Record of a tool execution for logging and dashboard."""

    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    latency_ms: int | None
