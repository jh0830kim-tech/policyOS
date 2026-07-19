from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain import UsageMetadata
from app.ai.model_gateway import ModelErrorCode, ModelGatewayError
from app.models.ai_execution import AgentRunRecord, AITaskRecord
from app.schemas.ai_task import AgentRunUsageRead
from app.services.ai_execution import AIExecutionRepository


@pytest.mark.asyncio
async def test_finish_run_persists_validated_usage_only() -> None:
    db = AsyncMock(spec=AsyncSession)
    run = AgentRunRecord(
        organization_id=uuid4(),
        task_id=uuid4(),
        agent_name="policy_research",
        prompt_version="1.0.0",
        prompt_hash="a" * 64,
    )
    usage = UsageMetadata(
        provider="openai",
        model="test-model",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        cached_input_tokens=40,
        duration_ms=250,
        retry_count=1,
        estimated_cost=0.0125,
    )
    await AIExecutionRepository(db).finish_run(
        run,
        status="succeeded",
        review_status="pending",
        provider_request_id="resp_safe",
        usage=usage,
    )
    assert run.provider == "openai"
    assert run.provider_response_id == "resp_safe"
    assert run.total_tokens == 120
    assert run.cached_input_tokens == 40
    assert run.latency_ms == 250
    assert run.retry_count == 1
    assert run.estimated_cost == Decimal("0.0125")
    db.commit.assert_awaited_once()


def test_usage_columns_and_aggregation_indexes() -> None:
    columns = set(AgentRunRecord.__table__.columns.keys())
    assert {
        "provider",
        "provider_response_id",
        "model_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "latency_ms",
        "retry_count",
        "estimated_cost",
    } <= columns
    run_indexes = {index.name for index in AgentRunRecord.__table__.indexes}
    task_indexes = {index.name for index in AITaskRecord.__table__.indexes}
    assert "ix_agent_runs_org_provider_model" in run_indexes
    assert "ix_agent_runs_org_started" in run_indexes
    assert "ix_ai_tasks_org_requesting_user" in task_indexes


def test_public_usage_summary_excludes_internal_and_sensitive_metadata() -> None:
    fields = set(AgentRunUsageRead.model_fields)
    for prohibited in (
        "provider_response_id",
        "provider_request_id",
        "prompt",
        "prompt_hash",
        "api_key",
        "bearer_token",
        "raw_provider_response",
        "reasoning",
    ):
        assert prohibited not in fields


def test_usage_migration_is_reversible_and_contains_no_sensitive_payloads() -> None:
    migration = Path("alembic/versions/20260720_0004_agent_run_usage_telemetry.py").read_text(
        encoding="utf-8"
    )
    for required in (
        '"provider_response_id"',
        '"cached_input_tokens"',
        '"estimated_cost"',
        '"ix_ai_tasks_org_requesting_user"',
        '"ix_agent_runs_org_provider_model"',
    ):
        assert required in migration
    for prohibited in ("raw_provider_response", "api_key", "bearer_token", "reasoning"):
        assert prohibited not in migration


@pytest.mark.asyncio
async def test_provider_failure_and_cancellation_telemetry() -> None:
    db = AsyncMock(spec=AsyncSession)
    repository = AIExecutionRepository(db)
    failed = AgentRunRecord(
        organization_id=uuid4(),
        task_id=uuid4(),
        agent_name="legal_review",
        prompt_version="1.0.0",
        prompt_hash="b" * 64,
        provider="openai",
    )
    error = ModelGatewayError(
        ModelErrorCode.RATE_LIMITED,
        "Model provider is rate limited",
        retryable=True,
        provider_request_id="resp_failed",
        retry_count=2,
        latency_ms=350,
        retry_after_seconds=1.0,
    )
    await repository.finish_run(
        failed,
        status="failed",
        review_status="pending",
        provider_error=error,
    )
    assert failed.status == "failed"
    assert failed.error_code == "rate_limited"
    assert failed.provider_response_id == "resp_failed"
    assert failed.retry_count == 2
    assert failed.latency_ms == 350

    cancelled = AgentRunRecord(
        organization_id=uuid4(),
        task_id=uuid4(),
        agent_name="statistics",
        prompt_version="1.0.0",
        prompt_hash="c" * 64,
    )
    await repository.cancel_run(cancelled)
    assert cancelled.status == "cancelled"
    assert cancelled.error_code == "cancelled"
