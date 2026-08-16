"""Security regression tests for stored XSS and security headers."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_security_headers_present(client: TestClient):
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_lead_payload_is_returned_literally(client: TestClient):
    """Payload must be returned verbatim so the frontend can use textContent."""
    payload = "<script>alert(1)</script>"
    chat = client.post(
        "/api/v1/chat",
        json={
            "conversation_id": "conv_xss",
            "message": f"У нас магазин, 2000 заявок. Компания {payload}",
        },
    )
    assert chat.status_code == 200
    lead_id = chat.json()["lead_id"]

    # Patch company with payload via operator API.
    patch = client.patch(f"/api/v1/leads/{lead_id}", json={"company": payload})
    assert patch.status_code == 200

    response = client.get(f"/api/v1/leads/{lead_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["company"] == payload
