"""Tests for leads, events, and conversations endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_leads_crud_and_events(client: TestClient):
    # Create a lead via chat.
    client.post(
        "/chat",
        json={
            "conversation_id": "conv_leads_api",
            "message": "У нас интернет-магазин, 2000 заявок. Хотим автоматически квалифицировать.",
        },
    )

    leads = client.get("/leads").json()
    assert len(leads) >= 1
    lead_id = leads[0]["id"]

    detail = client.get(f"/leads/{lead_id}").json()
    assert detail["id"] == lead_id
    assert detail["business_problem"] is not None

    events = client.get(f"/leads/{lead_id}/events").json()
    assert any(e["event_type"] == "lead_created" for e in events)

    patch = client.patch(
        f"/leads/{lead_id}", json={"fields": {"company": "TestCo"}}
    )
    assert patch.status_code == 200
    assert patch.json()["company"] == "TestCo"


@pytest.mark.asyncio
async def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
