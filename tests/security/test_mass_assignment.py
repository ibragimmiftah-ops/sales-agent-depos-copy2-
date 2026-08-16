"""Security regression tests for mass assignment and tool scope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_patch_lead_rejects_score_and_status(client: TestClient):
    # Create lead via chat.
    chat = client.post(
        "/api/v1/chat",
        json={
            "conversation_id": "conv_mass",
            "message": "У нас магазин, 2000 заявок. Хотим автоматизировать.",
        },
    )
    lead_id = chat.json()["lead_id"]

    response = client.patch(
        f"/api/v1/leads/{lead_id}", json={"lead_score": 100, "status": "qualified"}
    )
    assert response.status_code == 422
