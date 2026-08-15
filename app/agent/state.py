"""Lead state machine and stage transition rules."""

from __future__ import annotations

from app.core.logging import get_logger
from app.models import LeadStatus

logger = get_logger(__name__)


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    LeadStatus.NEW.value: {
        LeadStatus.ENGAGED.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.CLOSED.value,
    },
    LeadStatus.ENGAGED.value: {
        LeadStatus.QUALIFICATION.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.CLOSED.value,
    },
    LeadStatus.QUALIFICATION.value: {
        LeadStatus.QUALIFIED.value,
        LeadStatus.UNQUALIFIED.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.CLOSED.value,
    },
    LeadStatus.QUALIFIED.value: {
        LeadStatus.MEETING_PROPOSED.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.CLOSED.value,
    },
    LeadStatus.MEETING_PROPOSED.value: {
        LeadStatus.MEETING_BOOKED.value,
        LeadStatus.QUALIFIED.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.CLOSED.value,
    },
    LeadStatus.MEETING_BOOKED.value: {LeadStatus.CLOSED.value},
    LeadStatus.UNQUALIFIED.value: {LeadStatus.CLOSED.value, LeadStatus.QUALIFICATION.value},
    LeadStatus.NOT_INTERESTED.value: {LeadStatus.CLOSED.value},
    LeadStatus.CLOSED.value: set(),
}


class LeadStateMachine:
    """Validates and applies funnel stage transitions."""

    @staticmethod
    def can_transition(from_stage: str, to_stage: str) -> bool:
        if from_stage == to_stage:
            return True
        allowed = ALLOWED_TRANSITIONS.get(from_stage, set())
        return to_stage in allowed

    @staticmethod
    def normalize(stage: str | LeadStatus) -> str:
        if isinstance(stage, LeadStatus):
            return stage.value
        return stage

    @classmethod
    def validate(cls, from_stage: str | LeadStatus, to_stage: str | LeadStatus) -> str:
        from_s = cls.normalize(from_stage)
        to_s = cls.normalize(to_stage)
        if not cls.can_transition(from_s, to_s):
            raise ValueError(f"Invalid stage transition: {from_s} -> {to_s}")
        return to_s
