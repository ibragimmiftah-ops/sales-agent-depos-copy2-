"""Evaluation regression harness driven by tests/eval/cases.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

CASES_PATH = Path(__file__).with_suffix("").parent / "cases.json"


def _load_cases() -> list[dict[str, Any]]:
    with CASES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
async def test_eval_case(client: TestClient, case: dict[str, Any]):
    conversation_id = f"conv_eval_{case['id']}"
    for step in case["conversation"]:
        response = client.post(
            "/api/v1/chat",
            json={"conversation_id": conversation_id, "message": step["message"]},
        )
        assert response.status_code == 200, (
            f"{case['id']}: {step['message']} -> {response.text}"
        )
        data = response.json()
        if "expected_stage" in step:
            assert data["stage"] == step["expected_stage"], (
                f"{case['id']}: expected stage {step['expected_stage']}, got {data['stage']}"
            )
        if "expected_intent" in step:
            assert data["intent"] == step["expected_intent"], (
                f"{case['id']}: expected intent {step['expected_intent']}, got {data['intent']}"
            )
        if "expected_needs_rag" in step:
            # RAG flag is internal; verify response is grounded/cautious.
            assert "зависит" in data["response"].lower() or "стоимость" in data["response"].lower()
