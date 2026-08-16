"""Deterministic business policy: stage transitions and meeting eligibility."""

from __future__ import annotations

from app.core.logging import get_logger
from app.models import Lead, LeadStatus

logger = get_logger(__name__)

MIN_BOOKING_SCORE = 70


# Forward-only state machine with restricted jumps.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    LeadStatus.NEW.value: {
        LeadStatus.ENGAGED.value,
        LeadStatus.QUALIFICATION.value,
        LeadStatus.UNQUALIFIED.value,
        LeadStatus.NOT_INTERESTED.value,
    },
    LeadStatus.ENGAGED.value: {
        LeadStatus.QUALIFICATION.value,
        LeadStatus.UNQUALIFIED.value,
        LeadStatus.NOT_INTERESTED.value,
    },
    LeadStatus.QUALIFICATION.value: {
        LeadStatus.QUALIFIED.value,
        LeadStatus.UNQUALIFIED.value,
        LeadStatus.NOT_INTERESTED.value,
    },
    LeadStatus.QUALIFIED.value: {
        LeadStatus.MEETING_PROPOSED.value,
        LeadStatus.NOT_INTERESTED.value,
    },
    LeadStatus.MEETING_PROPOSED.value: {
        LeadStatus.MEETING_BOOKED.value,
        LeadStatus.QUALIFIED.value,
        LeadStatus.NOT_INTERESTED.value,
    },
    LeadStatus.MEETING_BOOKED.value: {LeadStatus.CLOSED.value},
    LeadStatus.UNQUALIFIED.value: {
        LeadStatus.QUALIFICATION.value,
        LeadStatus.NOT_INTERESTED.value,
    },
    LeadStatus.NOT_INTERESTED.value: {LeadStatus.CLOSED.value},
    LeadStatus.CLOSED.value: set(),
}


class LeadPolicy:
    """Deterministic policy for lead stage transitions and meeting eligibility."""

    @staticmethod
    def can_transition(from_stage: str, to_stage: str) -> bool:
        if from_stage == to_stage:
            return True
        allowed = ALLOWED_TRANSITIONS.get(from_stage, set())
        return to_stage in allowed

    @classmethod
    def validate_transition(cls, from_stage: str, to_stage: str) -> str:
        if not cls.can_transition(from_stage, to_stage):
            raise ValueError(f"Invalid stage transition: {from_stage} -> {to_stage}")
        return to_stage

    @classmethod
    def propose_stage(
        cls,
        lead: Lead,
        llm_proposed_stage: str,
        *,
        tool_succeeded: bool = True,
        booking_requested: bool = False,
    ) -> LeadStatus:
        """Return the stage that may actually be applied.

        LLM proposals are treated as suggestions only. Meeting_booked is only
        allowed after a successful booking tool result.
        """
        current = lead.status or LeadStatus.NEW.value

        # Never allow jumping directly to booked without a verified booking.
        if llm_proposed_stage == LeadStatus.MEETING_BOOKED.value and not tool_succeeded:
            logger.warning(
                "policy_rejected_direct_booking_jump",
                lead_id=lead.id,
                current=current,
            )
            return LeadStatus(current)

        # Booking can only be requested from qualified or meeting_proposed.
        if (
            booking_requested
            and current not in (LeadStatus.QUALIFIED.value, LeadStatus.MEETING_PROPOSED.value)
        ):
            logger.warning(
                "policy_rejected_booking_from_unqualified",
                lead_id=lead.id,
                current=current,
            )
            return LeadStatus(current)

        if cls.can_transition(current, llm_proposed_stage):
            return LeadStatus(llm_proposed_stage)

        logger.warning(
            "policy_rejected_invalid_transition",
            lead_id=lead.id,
            from_stage=current,
            to_stage=llm_proposed_stage,
        )
        return LeadStatus(current)

    @staticmethod
    def is_meeting_eligible(lead: Lead) -> bool:
        """Check whether the lead is allowed to book a meeting."""
        score_ok = lead.lead_score is not None and lead.lead_score >= MIN_BOOKING_SCORE
        has_problem = bool(lead.business_problem)
        has_contact = bool(lead.email) or bool(lead.phone)
        has_budget = bool(lead.budget_range)
        has_authority = lead.decision_maker is True
        return score_ok and has_problem and has_contact and has_budget and has_authority

    @staticmethod
    def meeting_eligibility_reasons(lead: Lead) -> list[str]:
        """Return missing eligibility criteria for user-facing feedback."""
        reasons = []
        if lead.lead_score is None or lead.lead_score < MIN_BOOKING_SCORE:
            reasons.append("insufficient lead score")
        if not lead.business_problem:
            reasons.append("business problem not collected")
        if not lead.email and not lead.phone:
            reasons.append("contact information missing")
        if not lead.budget_range:
            reasons.append("budget not provided")
        if lead.decision_maker is not True:
            reasons.append("decision-maker authority not confirmed")
        return reasons
