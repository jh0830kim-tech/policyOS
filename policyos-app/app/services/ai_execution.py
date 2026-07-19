import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_execution import AgentRunRecord, AITaskRecord


class AIExecutionRepository:
    """Organization-scoped execution persistence with explicit commits."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_task(
        self,
        *,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        task_type: str,
        parent_task_id: uuid.UUID | None = None,
    ) -> AITaskRecord:
        record = AITaskRecord(
            organization_id=organization_id,
            requesting_user_id=requesting_user_id,
            task_type=task_type,
            parent_task_id=parent_task_id,
        )
        self.db.add(record)
        await self.db.commit()
        return record

    async def get_task(self, task_id: uuid.UUID, organization_id: uuid.UUID) -> AITaskRecord | None:
        statement = select(AITaskRecord).where(
            AITaskRecord.id == task_id,
            AITaskRecord.organization_id == organization_id,
        )
        return await self.db.scalar(statement)

    async def start_run(
        self,
        *,
        organization_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_name: str,
        prompt_version: str,
        prompt_hash: str,
        parent_run_id: uuid.UUID | None = None,
        model_id: str | None = None,
    ) -> AgentRunRecord:
        record = AgentRunRecord(
            organization_id=organization_id,
            task_id=task_id,
            parent_run_id=parent_run_id,
            agent_name=agent_name,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            model_id=model_id,
        )
        self.db.add(record)
        await self.db.commit()
        return record

    async def finish_run(
        self,
        run: AgentRunRecord,
        *,
        status: str,
        review_status: str,
        result_summary: str | None = None,
        artifact_reference: str | None = None,
        error_code: str | None = None,
        provider_request_id: str | None = None,
    ) -> AgentRunRecord:
        run.status = status
        run.review_status = review_status
        run.result_summary = result_summary
        run.artifact_reference = artifact_reference
        run.error_code = error_code
        run.provider_request_id = provider_request_id
        run.finished_at = datetime.now(UTC)
        await self.db.commit()
        return run
