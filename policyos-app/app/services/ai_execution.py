import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain import UsageMetadata
from app.ai.model_gateway import ModelGatewayError
from app.models.ai_execution import AgentRunRecord, AITaskRecord


class AIExecutionRepository:
    """Organization-scoped execution persistence with explicit commit control."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_task(
        self,
        *,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        task_type: str,
        parent_task_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> AITaskRecord:
        record = AITaskRecord(
            organization_id=organization_id,
            requesting_user_id=requesting_user_id,
            task_type=task_type,
            parent_task_id=parent_task_id,
        )
        self.db.add(record)
        await self._persist(commit)
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
        provider: str | None = None,
        commit: bool = True,
    ) -> AgentRunRecord:
        record = AgentRunRecord(
            organization_id=organization_id,
            task_id=task_id,
            parent_run_id=parent_run_id,
            agent_name=agent_name,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            model_id=model_id,
            provider=provider,
        )
        self.db.add(record)
        await self._persist(commit)
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
        usage: UsageMetadata | None = None,
        provider_error: ModelGatewayError | None = None,
        commit: bool = True,
    ) -> AgentRunRecord:
        run.status = status
        run.review_status = review_status
        run.result_summary = result_summary
        run.artifact_reference = artifact_reference
        run.error_code = error_code
        run.provider_response_id = provider_request_id
        if provider_error is not None:
            run.error_code = provider_error.code.value
            run.provider_response_id = provider_error.provider_request_id
            run.retry_count = provider_error.retry_count
            run.latency_ms = provider_error.latency_ms
        if usage is not None:
            run.provider = usage.provider
            run.model_id = usage.model or run.model_id
            run.input_tokens = usage.input_tokens
            run.output_tokens = usage.output_tokens
            run.total_tokens = usage.total_tokens
            run.cached_input_tokens = usage.cached_input_tokens
            run.latency_ms = usage.duration_ms
            run.retry_count = usage.retry_count
            run.estimated_cost = (
                Decimal(str(usage.estimated_cost)) if usage.estimated_cost is not None else None
            )
        run.finished_at = datetime.now(UTC)
        await self._persist(commit)
        return run

    async def cancel_run(self, run: AgentRunRecord, *, commit: bool = True) -> AgentRunRecord:
        return await self.finish_run(
            run,
            status="cancelled",
            review_status="pending",
            error_code="cancelled",
            commit=commit,
        )

    async def _persist(self, commit: bool) -> None:
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
