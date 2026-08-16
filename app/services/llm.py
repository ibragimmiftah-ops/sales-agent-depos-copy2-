"""LLM provider abstraction with structured-output support."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract LLM provider. Implementations must be swappable via env config."""

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Return a dict validated by the Pydantic schema."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str:
        """Return plain text."""
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for OpenAI provider") from exc

        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise LLMError("OPENAI_API_KEY is not configured")
        self.client = openai.AsyncOpenAI(api_key=key)
        self.model = model or settings.LLM_MODEL
        self.default_temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        import openai

        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        system_msg = {
            "role": "system",
            "content": (
                "You must respond with a single JSON object matching this schema. "
                "Do not include markdown formatting or explanations.\n\n" + schema_json
            ),
        }
        full_messages = [system_msg, *messages]

        temp = temperature if temperature is not None else self.default_temperature
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    temperature=temp,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content or "{}"
                parsed = self._clean_and_parse(raw)
                validated = schema.model_validate(parsed)
                return validated.model_dump()
            except (openai.APIError, openai.APIConnectionError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning("openai_structured_attempt_failed", attempt=attempt, error=str(exc))
                continue
        raise LLMError(f"OpenAI structured call failed after retries: {last_error}")

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str:
        import openai

        temp = temperature if temperature is not None else self.default_temperature
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""
        except (openai.APIError, openai.APIConnectionError) as exc:
            logger.error("openai_completion_failed", error=str(exc))
            raise LLMError(f"OpenAI completion failed: {exc}") from exc

    @staticmethod
    def _clean_and_parse(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?", "", raw)
            raw = raw.rstrip("`").strip()
        return json.loads(raw)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("anthropic package is required for Anthropic provider") from exc

        key = api_key or settings.ANTHROPIC_API_KEY
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not configured")
        self.client = anthropic.AsyncAnthropic(api_key=key)
        self.model = model or settings.LLM_MODEL
        self.default_temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        import anthropic

        tool_name = "agent_decision"
        tool_schema = schema.model_json_schema()
        system_text = (
            "You are an AI Sales Agent for NovaFlow AI. Use the agent_decision tool."
        )
        temp = temperature if temperature is not None else self.default_temperature
        try:
            response = await self.client.messages.create(
                model=self.model,
                system=system_text,
                messages=messages,
                temperature=temp,
                max_tokens=self.max_tokens,
                tools=[{"name": tool_name, "input_schema": tool_schema}],
                tool_choice={"type": "tool", "name": tool_name},
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    validated = schema.model_validate(block.input)
                    return validated.model_dump()
            raise LLMError("Anthropic response did not contain expected tool_use block")
        except anthropic.APIError as exc:
            logger.error("anthropic_structured_failed", error=str(exc))
            raise LLMError(f"Anthropic structured call failed: {exc}") from exc

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str:
        import anthropic

        temp = temperature if temperature is not None else self.default_temperature
        try:
            response = await self.client.messages.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=self.max_tokens,
            )
            return "".join(b.text for b in response.content if b.type == "text")
        except anthropic.APIError as exc:
            logger.error("anthropic_completion_failed", error=str(exc))
            raise LLMError(f"Anthropic completion failed: {exc}") from exc


class MockLLMProvider(LLMProvider):
    """Deterministic provider for tests and local demos without API keys."""

    def __init__(self) -> None:
        self._sequence: list[dict[str, Any]] = []
        self._sequence_index = 0

    def set_decision_sequence(self, decisions: list[dict[str, Any]]) -> None:
        self._sequence = decisions
        self._sequence_index = 0

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        if self._sequence:
            decision = self._sequence[self._sequence_index % len(self._sequence)]
            self._sequence_index += 1
            validated = schema.model_validate(decision)
            return validated.model_dump()

        # Fallback keyword-based decision. Use the most recent user message.
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break
        return self._keyword_decision(user_text)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str:
        # Extract the draft response injected by the agent into the system prompt.
        marker = "Agent draft response:"
        for m in reversed(messages):
            content = m.get("content") or ""
            if marker in content:
                idx = content.index(marker) + len(marker)
                draft = content[idx:].strip()
                if draft:
                    return draft
        return "Спасибо за информацию. Чем ещё могу помочь?"

    @staticmethod
    def _keyword_decision(user_text: str) -> dict[str, Any]:
        text = user_text.lower()

        def _mu(field: str, value: Any) -> list[dict[str, Any]]:
            return [{"field": field, "value": value}]

        if any(w in text for w in ["цена", "стоит", "pricing", "price", "сколько"]):
            return {
                "intent": "pricing_question",
                "stage": "engaged",
                "needs_rag": True,
                "rag_query": "сколько стоит AI Sales Agent",
                "rag_category": "pricing",
                "tool": None,
                "tool_arguments": {},
                "memory_updates": [],
                "missing_fields": ["business_problem"],
                "lead_score_required": False,
                "next_best_action": "ask_business_problem",
                "should_offer_meeting": False,
                "response": "Точная стоимость зависит от объема интеграций и сценариев. Для ориентировочной оценки мне нужно понять, какие процессы вы хотите автоматизировать.",
            }

        if any(w in text for w in ["автоматиз", "обработк", "заявок", "лидов", "sales agent", "внедр"]):
            return {
                "intent": "new_lead",
                "stage": "qualification",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": _mu("business_problem", user_text),
                "missing_fields": ["channels", "monthly_leads"],
                "lead_score_required": False,
                "next_best_action": "ask_channel",
                "should_offer_meeting": False,
                "response": "Понял. Откуда сейчас в основном приходят заявки — сайт, Telegram, WhatsApp или другие каналы?",
            }

        if any(w in text for w in ["привет", "здравствуй", "hi", "hello"]):
            return {
                "intent": "greeting",
                "stage": "engaged",
                "needs_rag": False,
                "tool": None,
                "tool_arguments": {},
                "memory_updates": [],
                "missing_fields": ["business_problem"],
                "lead_score_required": False,
                "next_best_action": "ask_business_problem",
                "should_offer_meeting": False,
                "response": "Привет! Расскажите, какую задачу хотите решить с помощью AI-автоматизации?",
            }

        if any(w in text for w in ["whatsapp", "telegram", "сайт", "email", "instagram", "звонки"]):
            memory_updates: list[dict[str, Any]] = _mu("channels", [user_text])
            digits = re.findall(r"\d+", text)
            if digits:
                memory_updates.append({"field": "monthly_leads", "value": int(digits[0])})
            return {
                "intent": "qualification_answer",
                "stage": "qualification",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": memory_updates,
                "missing_fields": ["current_software"] if digits else ["monthly_leads"],
                "lead_score_required": bool(digits),
                "next_best_action": "ask_current_software" if digits else "ask_volume",
                "should_offer_meeting": False,
                "response": "Спасибо. А какую CRM или систему для учёта заявок используете сейчас?" if digits else "Понял. Примерно сколько входящих заявок вы получаете в месяц?",
            }

        if re.search(r"\d+", text) and any(w in text for w in ["в месяц", "месяц", "заявок", "обращен"]):
            digits = re.findall(r"\d+", text)
            volume = int(digits[0]) if digits else None
            return {
                "intent": "qualification_answer",
                "stage": "qualification",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": _mu("monthly_leads", volume),
                "missing_fields": ["current_software", "budget_range"],
                "lead_score_required": True,
                "next_best_action": "ask_current_software",
                "should_offer_meeting": False,
                "response": "Спасибо. А какую CRM или систему для учёта заявок используете сейчас?",
            }

        if any(w in text for w in ["bitrix", "битрикс", "hubspot", "amo", "zoho", "salesforce", "excel", "google sheet"]):
            return {
                "intent": "qualification_answer",
                "stage": "qualification",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": _mu("current_software", user_text),
                "missing_fields": ["budget_range"],
                "lead_score_required": True,
                "next_best_action": "ask_budget",
                "should_offer_meeting": False,
                "response": "Понятно. Какой бюджет вы рассматриваете на внедрение?",
            }

        if any(w in text for w in ["бюджет", "budget", "готовы", "евро", "€", "руб", "тенге", "usd"]):
            return {
                "intent": "qualification_answer",
                "stage": "qualification",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": [
                    {"field": "budget_range", "value": user_text},
                    {"field": "urgency", "value": "1-3 months"},
                ],
                "missing_fields": ["decision_maker"],
                "lead_score_required": True,
                "next_best_action": "ask_authority",
                "should_offer_meeting": False,
                "response": "Понял. Принимаете ли вы финальное решение по такому проекту?",
            }

        if any(w in text for w in ["я принимаю", "owner", "руководитель", "директор", "основатель", "decision maker"]):
            return {
                "intent": "qualification_answer",
                "stage": "qualified",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": _mu("decision_maker", True),
                "missing_fields": ["email"],
                "lead_score_required": True,
                "next_best_action": "request_contact",
                "should_offer_meeting": False,
                "response": "Для бронирования созвона укажите, пожалуйста, email.",
            }

        if "@" in text and "." in text:
            # crude email detection
            import re as _re
            email_match = _re.search(r"[\w.-]+@[\w.-]+\.\w+", text)
            email = email_match.group(0) if email_match else text.strip()
            return {
                "intent": "contact_information",
                "stage": "qualified",
                "needs_rag": False,
                "tool": "update_lead",
                "tool_arguments": {},
                "memory_updates": _mu("email", email),
                "missing_fields": [],
                "lead_score_required": False,
                "next_best_action": "offer_meeting",
                "should_offer_meeting": True,
                "response": "Спасибо. Могу предложить несколько свободных слотов для 30-минутного созвона.",
            }

        if any(w in text for w in ["давайте", "предлож", "слот", "встреч"]):
            return {
                "intent": "meeting_request",
                "stage": "meeting_proposed",
                "needs_rag": False,
                "tool": "get_available_slots",
                "tool_arguments": {},
                "memory_updates": [],
                "missing_fields": [],
                "lead_score_required": False,
                "next_best_action": "get_available_slots",
                "should_offer_meeting": False,
                "response": "Вот несколько ближайших слотов. Выберите удобное время:",
            }

        datetime_match = re.search(
            r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2})?",
            text,
        )
        if datetime_match:
            return {
                "intent": "meeting_selection",
                "stage": "meeting_booked",
                "needs_rag": False,
                "tool": "book_meeting",
                "tool_arguments": {"datetime": datetime_match.group(0).upper()},
                "memory_updates": [],
                "missing_fields": [],
                "lead_score_required": False,
                "next_best_action": "book_meeting",
                "should_offer_meeting": False,
                "response": "Отлично, встреча забронирована. Скоро пришлю подтверждение на почту.",
            }

        return {
            "intent": "other",
            "stage": "engaged",
            "needs_rag": False,
            "tool": None,
            "tool_arguments": {},
            "memory_updates": [],
            "missing_fields": ["business_problem"],
            "lead_score_required": False,
            "next_best_action": "continue_conversation",
            "should_offer_meeting": False,
            "response": "Понял. Расскажите подробнее о вашем бизнесе и задаче, которую хотите решить?",
        }


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "mock":
        return MockLLMProvider()
    raise ValueError(f"Unknown LLM provider: {provider}")
