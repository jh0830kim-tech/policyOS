from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai_task import AgentRunUsageRead, AITaskCreate, AITaskRead


def test_ai_task_endpoint_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ai/tasks", params={"organization_id": str(uuid4())})
    assert response.status_code == 401


def test_ai_task_input_is_bounded() -> None:
    assert AITaskCreate.model_fields["instruction"].metadata


def test_public_response_excludes_sensitive_internal_fields() -> None:
    fields = set(AITaskRead.model_fields)
    for prohibited in (
        "instruction",
        "system_prompt",
        "prompt_hash",
        "provider_payload",
        "api_key",
        "reasoning",
    ):
        assert prohibited not in fields


def test_ai_task_routes_are_visible_in_openapi() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/ai/tasks" in paths
    assert "/api/v1/ai/tasks/{task_id}" in paths
    assert "/api/v1/ai/tasks/{task_id}/usage" in paths


def test_usage_api_schema_exposes_summary_only() -> None:
    fields = set(AgentRunUsageRead.model_fields)
    assert {"provider", "model_id", "total_tokens", "latency_ms", "status"} <= fields
    assert "provider_response_id" not in fields
    assert "prompt_hash" not in fields
