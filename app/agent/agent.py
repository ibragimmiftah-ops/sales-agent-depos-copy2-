"""Core agent loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import build_decision_messages, build_response_messages
from app.agent.schemas import AgentDecision, AgentState, TOOLS
from app.agent.state import LeadStateMachine
from app.core.config import settings
from app.core.exceptions import LLMError, ToolError
from app.core.logging import get_logger
from app.memory.long_term import collect_collected_fields
from app.memory.short_term import ShortTermMemory
from app.models import Conversation, Lead, LeadStatus, Message
from app.rag.retrieval import KnowledgeRetriever
from app.services.calendar import CalendarService
from app.services.crm import CRMService
from app.services.llm import LLMProvider, get_llm_provider
from app.tools import TOOL_REGISTRY
from app.tools.base import ToolContext

logger = get_logger(__name__)


class SalesAgent:
    """AI Sales Agent orchestrating intent, RAG, tools, state, and response."""

    def __init__(
        self,
        llm: LLMProvider | None = None,
        retriever: KnowledgeRetriever | None = None,
        short_term: ShortTermMemory | None = None,
        calendar_service: CalendarService | None = None,
    ):
        self.llm = llm or get_llm_provider()
        self.retriever = retriever or KnowledgeRetriever()
        self.short_term = short_term or ShortTermMemory()
        self.calendar_service = calendar_service or CalendarService()
        self.tool_context = ToolContext(
            session=None,  # type: ignore[arg-type]
            retriever=self.retriever,
            calendar_service=self.calendar_service,
        )

    async def handle(
        self, session: AsyncSession, conversation_id: str, user_message: str
    ) -> AgentState:
        start_time = datetime.now(timezone.utc)
        tool_results: list[dict[str, Any]] = []
        rag_context: str | None = None

        # Load/create lead and conversation.
        lead = await CRMService.get_or_create_conversation_lead(session, conversation_id)
        conversation_result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conversation_result.scalar_one_or_none()
        if conversation is None:
            conversation = Conversation(id=conversation_id, lead_id=lead.id)
            session.add(conversation)
            await session.flush()

        # Persist user message and update history.
        session.add(
            Message(
                conversation_id=conversation_id,
                role="user",
                content=user_message,
            )
        )
        await self.short_term.add_message(conversation_id, "user", user_message)
        history = await self.short_term.get_messages(conversation_id)

        # ------------------------------------------------------------------
        # 1. Decision call
        # ------------------------------------------------------------------
        try:
            decision_messages = build_decision_messages(user_message, lead, history)
            decision_raw = await self.llm.complete_structured(
                decision_messages, AgentDecision
            )
            decision = AgentDecision.model_validate(decision_raw)
        except (LLMError, Exception) as exc:
            logger.error("decision_call_failed", error=str(exc))
            decision = self._fallback_decision(user_message, lead)

        # ------------------------------------------------------------------
        # 2. Apply memory updates (long-term memory)
        # ------------------------------------------------------------------
        if decision.memory_updates:
            normalized = self._normalize_memory_updates(decision.memory_updates)
            if normalized:
                await CRMService.update_lead(session, lead.id, normalized)
                logger.info("memory_updates_applied", lead_id=lead.id, fields=list(normalized.keys()))

        # ------------------------------------------------------------------
        # 3. Stage transition
        # ------------------------------------------------------------------
        if decision.stage != lead.status:
            try:
                LeadStateMachine.validate(lead.status, decision.stage)
                await CRMService.update_lead_status(
                    session,
                    lead.id,
                    LeadStatus(decision.stage),
                    reason=f"Agent decision: {decision.intent}",
                )
            except ValueError as exc:
                logger.warning(
                    "invalid_stage_transition",
                    lead_id=lead.id,
                    from_stage=lead.status,
                    to_stage=decision.stage,
                    error=str(exc),
                )

        # ------------------------------------------------------------------
        # 4. Execute tool if requested
        # ------------------------------------------------------------------
        if decision.tool and decision.tool in TOOLS:
            tool_args = self._inject_lead_id(
                decision.tool, decision.tool_arguments, lead
            )
            self.tool_context.session = session
            try:
                result = await TOOL_REGISTRY.execute(
                    self.tool_context, decision.tool, tool_args
                )
                tool_results.append(
                    {
                        "tool": decision.tool,
                        "arguments": tool_args,
                        "result": result,
                    }
                )
                logger.info("agent_tool_executed", tool=decision.tool, lead_id=lead.id)
            except ToolError as exc:
                tool_results.append(
                    {
                        "tool": decision.tool,
                        "arguments": tool_args,
                        "error": str(exc),
                    }
                )
                logger.error("agent_tool_failed", tool=decision.tool, error=str(exc))

        # ------------------------------------------------------------------
        # 5. RAG retrieval if needed
        # ------------------------------------------------------------------
        if decision.needs_rag:
            try:
                rag_context = await self.retriever.search_to_context(
                    query=decision.rag_query or user_message,
                    category=decision.rag_category,
                    top_k=5,
                )
            except Exception as exc:
                logger.error("rag_in_agent_failed", error=str(exc))
                rag_context = ""

        # ------------------------------------------------------------------
        # 6. Recalculate score if needed
        # ------------------------------------------------------------------
        if decision.lead_score_required:
            try:
                self.tool_context.session = session
                score_result = await TOOL_REGISTRY.execute(
                    self.tool_context,
                    "calculate_lead_score",
                    {"lead_id": lead.id},
                )
                tool_results.append(
                    {
                        "tool": "calculate_lead_score",
                        "arguments": {"lead_id": lead.id},
                        "result": score_result,
                    }
                )
            except Exception as exc:
                logger.error("score_recalculation_failed", error=str(exc))

        # ------------------------------------------------------------------
        # 7. Response generation
        # ------------------------------------------------------------------
        try:
            response_messages = build_response_messages(
                user_message,
                lead,
                decision.model_dump(),
                history,
                rag_context=rag_context or None,
                tool_result=tool_results[-1] if tool_results else None,
            )
            final_response = await self.llm.complete(response_messages)
            if not final_response.strip():
                final_response = decision.response
        except (LLMError, Exception) as exc:
            logger.error("response_generation_failed", error=str(exc))
            final_response = decision.response

        # ------------------------------------------------------------------
        # 8. Persist assistant message and final state
        # ------------------------------------------------------------------
        await CRMService.update_lead(
            session,
            lead.id,
            {"next_best_action": decision.next_best_action},
        )
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_response,
            intent=decision.intent,
            decision=decision.model_dump(),
        )
        session.add(assistant_message)
        await self.short_term.add_message(
            conversation_id,
            "assistant",
            final_response,
            intent=decision.intent,
            decision=decision.model_dump(),
        )

        await session.commit()

        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        logger.info(
            "agent_turn_complete",
            conversation_id=conversation_id,
            lead_id=lead.id,
            intent=decision.intent,
            stage=lead.status,
            latency_ms=latency_ms,
        )

        return AgentState(
            conversation_id=conversation_id,
            lead_id=lead.id,
            intent=decision.intent,
            stage=lead.status,
            lead_score=lead.lead_score,
            lead_quality=lead.lead_quality,
            next_best_action=decision.next_best_action,
            missing_fields=decision.missing_fields,
            collected_fields=collect_collected_fields(lead),
            last_tool_calls=tool_results,
            response=final_response,
        )

    @staticmethod
    def _fallback_decision(user_message: str, lead: Lead) -> AgentDecision:
        """Safe deterministic fallback if the LLM fails."""
        return AgentDecision(
            intent="other",
            stage=lead.status or LeadStatus.ENGAGED.value,
            needs_rag=False,
            tool=None,
            tool_arguments={},
            memory_updates={},
            missing_fields=["business_problem"],
            lead_score_required=False,
            next_best_action="continue_conversation",
            should_offer_meeting=False,
            response="Извините, не удалось обработать сообщение. Расскажите, пожалуйста, какую задачу вы хотите решить?",
        )

    @staticmethod
    def _normalize_memory_updates(updates: dict[str, Any]) -> dict[str, Any]:
        """Clean and coerce fields coming from the LLM."""
        normalized: dict[str, Any] = {}
        for key, value in updates.items():
            if value in (None, "", "null"):
                continue
            if key == "channels" and isinstance(value, str):
                normalized[key] = [v.strip() for v in value.split(",") if v.strip()]
            elif key == "monthly_leads":
                try:
                    normalized[key] = int(value)
                except (ValueError, TypeError):
                    continue
            elif key == "decision_maker" and isinstance(value, str):
                normalized[key] = value.lower() in ("true", "yes", "да", "1")
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _inject_lead_id(tool: str, arguments: dict[str, Any], lead: Lead) -> dict[str, Any]:
        """Ensure tool arguments contain lead_id when required."""
        args = dict(arguments)
        lead_id_tools = {
            "update_lead",
            "get_lead",
            "calculate_lead_score",
            "save_memory",
            "book_meeting",
        }
        if tool in lead_id_tools and "lead_id" not in args:
            args["lead_id"] = lead.id

        if tool == "get_available_slots":
            if "date_from" not in args:
                tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
                args["date_from"] = tomorrow.strftime("%Y-%m-%d")
            if "date_to" not in args:
                from_date = datetime.strptime(args["date_from"], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                args["date_to"] = (from_date + timedelta(days=3)).strftime("%Y-%m-%d")
            if "duration_minutes" not in args:
                args["duration_minutes"] = settings.SLOT_DURATION_MINUTES
            if "timezone" not in args:
                args["timezone"] = settings.DEFAULT_TIMEZONE

        if tool == "book_meeting":
            if "duration_minutes" not in args:
                args["duration_minutes"] = settings.SLOT_DURATION_MINUTES
            if "timezone" not in args:
                args["timezone"] = settings.DEFAULT_TIMEZONE
            if "name" not in args:
                args["name"] = lead.name or ""
            if "email" not in args:
                args["email"] = lead.email or ""

        return args


def get_sales_agent() -> SalesAgent:
    return SalesAgent()
