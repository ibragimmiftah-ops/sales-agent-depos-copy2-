"""Tests for the lead funnel state machine."""

import pytest

from app.agent.state import LeadStateMachine
from app.models import LeadStatus


@pytest.mark.parametrize(
    "from_stage,to_stage,expected",
    [
        (LeadStatus.NEW, LeadStatus.ENGAGED, True),
        (LeadStatus.NEW, LeadStatus.QUALIFICATION, True),
        (LeadStatus.QUALIFICATION, LeadStatus.QUALIFIED, True),
        (LeadStatus.QUALIFIED, LeadStatus.MEETING_BOOKED, True),
        (LeadStatus.MEETING_BOOKED, LeadStatus.NEW, False),
        (LeadStatus.CLOSED, LeadStatus.NEW, False),
    ],
)
def test_can_transition(from_stage, to_stage, expected):
    assert (
        LeadStateMachine.can_transition(from_stage.value, to_stage.value) == expected
    )


def test_validate_invalid_transition_raises():
    with pytest.raises(ValueError):
        LeadStateMachine.validate(LeadStatus.CLOSED, LeadStatus.NEW)
