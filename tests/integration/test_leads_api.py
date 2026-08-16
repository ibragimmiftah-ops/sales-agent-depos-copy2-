"""Tests for leads, events, and conversations endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_leads_crud_and_events(client: TestClient):
    # Create a lead via chat.
    client.post(
        "/api/v1/chat",
        json={
            "conversation_id": "conv_leads_api",
            "message": "У нас интернет-магазин, 2000 заявок. Хотим автоматически квалифицировать.",
        },
    )

    leads = client.get("/api/v1/leads").json()
    assert len(leads) >= 1
    lead_id = leads[0]["id"]

    detail = client.get(f"/api/v1/leads/{lead_id}").json()
    assert detail["id"] == lead_id
    assert detail["business_problem"] is not None

    events = client.get(f"/api/v1/leads/{lead_id}/events").json()
    assert any(e["event_type"] == "lead_created" for e in events)

    patch = client.patch(
        f"/api/v1/leads/{lead_id}", json={"company": "TestCo"}
    )
    assert patch.status_code == 200
    assert patch.json()["company"] == "TestCo"


@pytest.mark.asyncio
async def test_patch_rejects_internal_fields(client: TestClient):
    chat = client.post(
        "/api/v1/chat",
        json={
            "conversation_id": "conv_mass_int",
            "message": "У нас магазин, 2000 заявок. Хотим автоматизировать.",
        },
    )
    lead_id = chat.json()["lead_id"]
    response = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"status": "qualified", "lead_score": 100},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_anonymous_cannot_list_leads(client: TestClient, chat_token: str):
    response = client.get(
        "/api/v1/leads", headers={"Authorization": f"Bearer {chat_token}"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
