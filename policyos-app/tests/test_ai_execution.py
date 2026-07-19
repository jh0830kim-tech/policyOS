from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_execution import AgentRunRecord, AITaskRecord
from app.services.ai_execution import AIExecutionRepository


@pytest.mark.asyncio
async def test_create_task_commits() -> None:
    db = AsyncMock(spec=AsyncSession)
    repository = AIExecutionRepository(db)
    organization_id, user_id = uuid4(), uuid4()
    record = await repository.create_task(
        organization_id=organization_id, requesting_user_id=user_id, task_type="combined"
    )
    assert record.organization_id == organization_id
    db.add.assert_called_once_with(record)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_lookup_is_organization_scoped() -> None:
    db = AsyncMock(spec=AsyncSession)
    await AIExecutionRepository(db).get_task(uuid4(), uuid4())
    sql = str(db.scalar.await_args.args[0])
    assert "ai_tasks.id =" in sql
    assert "ai_tasks.organization_id =" in sql


@pytest.mark.asyncio
async def test_parent_run_and_error_transition() -> None:
    db = AsyncMock(spec=AsyncSession)
    repository = AIExecutionRepository(db)
    parent_id = uuid4()
    run = await repository.start_run(
        organization_id=uuid4(),
        task_id=uuid4(),
        parent_run_id=parent_id,
        agent_name="legal_review",
        prompt_version="1.0.0",
        prompt_hash="a" * 64,
    )
    await repository.finish_run(
        run, status="failed", review_status="pending", error_code="provider_unavailable"
    )
    assert run.parent_run_id == parent_id
    assert run.error_code == "provider_unavailable"
    assert run.finished_at is not None and run.finished_at.utcoffset() is not None
    assert db.commit.await_count == 2


def test_models_exclude_sensitive_payload_and_hidden_reasoning() -> None:
    columns = set(AITaskRecord.__table__.columns) | set(AgentRunRecord.__table__.columns)
    for prohibited in ("password", "token", "api_key", "instruction", "reasoning", "payload"):
        assert prohibited not in columns
