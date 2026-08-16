"""Tests for the deterministic lead policy."""

import pytest

from app.models import Lead, LeadStatus
from app.services.policy import LeadPolicy


@pytest.mark.parametrize(
    "from_stage,to_stage,expected",
    [
        (LeadStatus.NEW, LeadStatus.ENGAGED, True),
        (LeadStatus.NEW, LeadStatus.QUALIFICATION, True),
        (LeadStatus.QUALIFICATION, LeadStatus.QUALIFIED, True),
        (LeadStatus.QUALIFIED, LeadStatus.MEETING_PROPOSED, True),
        (LeadStatus.MEETING_PROPOSED, LeadStatus.MEETING_BOOKED, True),
        (LeadStatus.MEETING_BOOKED, LeadStatus.NEW, False),
        (LeadStatus.CLOSED, LeadStatus.NEW, False),
    ],
)
def test_can_transition(from_stage, to_stage, expected):
    assert (
        LeadPolicy.can_transition(from_stage.value, to_stage.value) == expected
    )


def test_validate_invalid_transition_raises():
    with pytest.raises(ValueError):
        LeadPolicy.validate_transition(LeadStatus.CLOSED.value, LeadStatus.NEW.value)


def test_direct_booking_jump_rejected():
    lead = Lead(status=LeadStatus.QUALIFIED.value, lead_score=75)
    proposed = LeadPolicy.propose_stage(
        lead, LeadStatus.MEETING_BOOKED.value, tool_succeeded=False
    )
    assert proposed.value == LeadStatus.QUALIFIED.value


def test_booking_eligibility():
    eligible = Lead(
        business_problem="slow leads",
        budget_range="50k+",
        email="a@example.com",
        decision_maker=True,
        lead_score=80,
    )
    assert LeadPolicy.is_meeting_eligible(eligible) is True

    ineligible = Lead(business_problem="slow leads")
    assert LeadPolicy.is_meeting_eligible(ineligible) is False
