"""End-to-end tests for the /api/v1/chat endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_demo_conversation_flow(client: TestClient):
    """Full demo scenario with operator token."""
    conversation_id = "conv_test_dental_001"
    steps = [
        (
            "Привет. У нас сеть стоматологий. Хотим автоматизировать обработку заявок.",
            "qualification",
        ),
        ("WhatsApp и сайт. Около 1500 в месяц.", "qualification"),
        ("Bitrix24", "qualification"),
        ("Бюджет 50k+", "qualification"),
        ("Да, я директор", "qualified"),
        ("manager@dentalpro.fi", "qualified"),
        ("давайте", "meeting_proposed"),
        ("2026-08-18T12:00:00+03:00", "meeting_booked"),
    ]

    for message, expected_stage in steps:
        response = client.post(
            "/api/v1/chat", json={"conversation_id": conversation_id, "message": message}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["conversation_id"] == conversation_id
        assert data["stage"] == expected_stage, (
            f"For message '{message}' expected {expected_stage}, got {data['stage']}"
        )

    final = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert len(final) == len(steps) * 2  # user + assistant per step
    assert final[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_pricing_question_uses_rag(client: TestClient):
    response = client.post(
        "/api/v1/chat",
        json={"conversation_id": "conv_test_pricing", "message": "Сколько стоит AI Sales Agent?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "pricing_question"
    assert "зависит" in data["response"].lower() or "стоимость" in data["response"].lower()


@pytest.mark.asyncio
async def test_anonymous_chat_cannot_access_leads(client: TestClient, chat_token: str):
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {chat_token}"})
    # Anonymous principals are rejected by require_authenticated before role checks.
    assert response.status_code == 401
