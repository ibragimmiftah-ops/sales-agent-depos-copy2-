"""Security regression tests for authentication and authorization."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_anonymous_access_to_leads_returns_401(anonymous_client: TestClient):
    response = anonymous_client.get("/api/v1/leads", headers={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_anonymous_access_to_events_returns_401(anonymous_client: TestClient):
    response = anonymous_client.get("/api/v1/leads/lead_x/events", headers={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_anonymous_access_to_conversations_returns_401(anonymous_client: TestClient):
    response = anonymous_client.get("/api/v1/conversations/conv_x", headers={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_allows_anonymous_with_public_token(
    anonymous_client: TestClient, chat_token: str
):
    response = anonymous_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {chat_token}"},
        json={"message": "Привет"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cross_tenant_access_is_isolated(
    anonymous_client: TestClient, operator_principal
):
    # Create a lead via chat in the operator's tenant.
    client_with_auth = anonymous_client
    client_with_auth.headers["Authorization"] = f"Bearer {operator_principal.token}"
    chat = client_with_auth.post(
        "/api/v1/chat",
        json={
            "conversation_id": "conv_sec_tenant",
            "message": "У нас интернет-магазин, 2000 заявок.",
        },
    )
    assert chat.status_code == 200
    lead_id = chat.json()["lead_id"]

    # Build a token for a different tenant.
    from app.core.security import Principal, create_access_token

    attacker = Principal(
        user_id="attacker",
        tenant_id="tenant_other",
        roles=frozenset(["operator"]),
        scopes=frozenset(["crm:read", "crm:write"]),
    )
    token = create_access_token(
        {
            "sub": attacker.user_id,
            "tenant_id": attacker.tenant_id,
            "roles": list(attacker.roles),
            "scopes": list(attacker.scopes),
        }
    )

    response = anonymous_client.get(
        f"/api/v1/leads/{lead_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
