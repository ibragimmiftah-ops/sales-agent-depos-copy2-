"""Tests for the configurable lead scoring engine."""

from __future__ import annotations

import pytest

from app.models import Lead
from app.tools.scoring import ScoringEngine


@pytest.fixture
def engine() -> ScoringEngine:
    return ScoringEngine()


@pytest.mark.asyncio
async def test_clear_problem_and_high_volume_scores_qualified(engine: ScoringEngine):
    lead = Lead(
        business_problem="slow lead processing",
        monthly_leads=2000,
        budget_range="50k+",
        urgency="нужно сейчас",
        decision_maker=True,
        industry="ecommerce",
    )
    result = engine.score(lead)
    assert result["lead_score"] >= 70
    assert result["lead_quality"] == "qualified"
    assert "decision maker identified" in result["reasons"]


@pytest.mark.asyncio
async def test_empty_lead_scores_low(engine: ScoringEngine):
    lead = Lead()
    result = engine.score(lead)
    assert result["lead_score"] < 40
    assert result["lead_quality"] == "low"
