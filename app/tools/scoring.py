"""Configurable lead scoring engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel as _BaseModel
from pydantic import Field

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Lead
from app.services.crm import CRMService
from app.tools.base import Tool, ToolContext, register_tool

logger = get_logger(__name__)


class ScoringEngine:
    """Calculates a 0-100 lead score from lead fields using YAML config."""

    def __init__(self, config_path: str | None = None):
        path = Path(config_path or settings.SCORING_CONFIG_PATH)
        if not path.exists():
            raise FileNotFoundError(f"Scoring config not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def score(self, lead: Lead) -> dict[str, Any]:
        """Return score, quality, and reasons."""
        score = 0
        reasons: list[str] = []
        c = self.config["criteria"]

        # Business need
        if lead.business_problem:
            score += c["business_need"]["clear_problem"]
            reasons.append("clear business problem")
        elif lead.desired_solution:
            score += c["business_need"]["general_interest"]
            reasons.append("general interest expressed")

        # Budget
        budget_status = self._classify_budget(lead.budget_range)
        score += c["budget"][budget_status]
        if budget_status == "suitable":
            reasons.append("budget range suitable")
        elif budget_status == "insufficient":
            reasons.append("budget range below engagement threshold")
        elif budget_status == "unknown":
            reasons.append("budget not yet provided")

        # Urgency
        urgency_status = self._classify_urgency(lead.urgency)
        score += c["urgency"][urgency_status]
        if urgency_status == "now":
            reasons.append("urgent implementation needed")
        elif urgency_status == "one_to_three_months":
            reasons.append("implementation within 1-3 months")

        # Authority
        authority_status = self._classify_authority(lead.decision_maker)
        score += c["authority"][authority_status]
        if authority_status == "decision_maker":
            reasons.append("decision maker identified")
        elif authority_status == "influencer":
            reasons.append("influences decision")

        # Company fit
        fit_status = self._classify_fit(lead.industry)
        score += c["company_fit"][fit_status]
        if fit_status == "good":
            reasons.append("good industry fit")
        elif fit_status == "partial":
            reasons.append("partial industry fit")

        # Volume / ROI potential
        volume_status = self._classify_volume(lead.monthly_leads)
        score += c["volume"][volume_status]
        if volume_status == "high":
            reasons.append("high lead volume")
        elif volume_status == "medium":
            reasons.append("medium lead volume")

        score = max(0, min(100, score))
        quality = self._quality(score)

        logger.info(
            "lead_scored",
            lead_id=lead.id,
            score=score,
            quality=quality,
            reasons=reasons,
        )
        return {
            "lead_score": score,
            "lead_quality": quality,
            "reasons": reasons,
        }

    def _classify_budget(self, budget: str | None) -> str:
        if not budget:
            return "unknown"
        b = budget.lower()
        for marker in self.config["budget"]["insufficient"]:
            if marker.lower() in b:
                return "insufficient"
        for marker in self.config["budget"]["suitable"]:
            if marker.lower() in b:
                return "suitable"
        return "suitable"  # any provided non-insufficient budget is assumed workable

    def _classify_urgency(self, urgency: str | None) -> str:
        if not urgency:
            return "someday"
        u = urgency.lower()
        for marker in self.config["urgency"]["now"]:
            if marker.lower() in u:
                return "now"
        for marker in self.config["urgency"]["one_to_three_months"]:
            if marker.lower() in u:
                return "one_to_three_months"
        return "someday"

    def _classify_authority(self, decision_maker: bool | None) -> str:
        if decision_maker is True:
            return "decision_maker"
        if decision_maker is False:
            return "none"
        return "none"

    def _classify_fit(self, industry: str | None) -> str:
        if not industry:
            return "none"
        ind = industry.lower()
        for marker in self.config["company_fit"]["good"]:
            if marker.lower() in ind:
                return "good"
        for marker in self.config["company_fit"]["partial"]:
            if marker.lower() in ind:
                return "partial"
        return "none"

    def _classify_volume(self, volume: int | None) -> str:
        if volume is None:
            return "low"
        if volume >= self.config["volume"]["high"]:
            return "high"
        if volume >= self.config["volume"]["medium"]:
            return "medium"
        return "low"

    def _quality(self, score: int) -> str:
        thresholds = self.config["thresholds"]
        if score <= thresholds["low"]:
            return "low"
        if score <= thresholds["potential"]:
            return "potential"
        return "qualified"


# ---------------------------------------------------------------------------
# Tool wrapper
# ---------------------------------------------------------------------------


class CalculateLeadScoreInput(_BaseModel):
    lead_id: str = Field(...)
    tenant_id: str = Field(...)


class CalculateLeadScoreTool(Tool[CalculateLeadScoreInput]):
    name = "calculate_lead_score"
    description = "Calculate or recalculate the lead score and quality."
    input_schema = CalculateLeadScoreInput

    async def execute(self, context: ToolContext, arguments: CalculateLeadScoreInput) -> dict[str, Any]:
        if arguments.tenant_id != context.principal.tenant_id:
            return {"success": False, "error": "Tenant mismatch"}
        lead = await CRMService.get_lead(
            context.session, arguments.lead_id, tenant_id=context.principal.tenant_id
        )
        if lead is None:
            return {"success": False, "error": f"Lead {arguments.lead_id} not found"}

        engine = ScoringEngine()
        result = engine.score(lead)
        await CRMService.update_lead(
            context.session,
            lead.id,
            tenant_id=context.principal.tenant_id,
            fields={
                "lead_score": result["lead_score"],
                "lead_quality": result["lead_quality"],
            },
            allowed_fields={"lead_score", "lead_quality"},
        )
        await CRMService.append_event(
            context.session,
            lead.id,
            tenant_id=context.principal.tenant_id,
            event_type="score_changed",
            payload=result,
        )
        return {"success": True, **result}


register_tool(CalculateLeadScoreTool())
