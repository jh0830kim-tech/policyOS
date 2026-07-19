"""Application service connecting configured providers to governed Office persistence."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.artifacts import (
    AgentResultArtifact,
    ArtifactMetadata,
    ArtifactReviewStatus,
    OfficeWorkPackage,
)
from app.ai.composition import OfficeComposition, build_office_composition
from app.ai.domain import AgentContext, AgentStatus, AgentTask
from app.ai.workflows import AGENT_CAPABILITIES, WORKFLOW_ROUTES
from app.core.config import Settings
from app.models.artifact import WorkPackageRecord
from app.schemas.artifact import WorkPackageCreate
from app.services.ai_execution import AIExecutionRepository
from app.services.artifacts import ArtifactRepository
from app.services.provider_privacy import ProviderAuditRepository


class OfficeExecutionError(Exception):
    def __init__(self, code: str, safe_message: str, http_status: int) -> None:
        self.code = code
        self.safe_message = safe_message
        self.http_status = http_status
        super().__init__(safe_message)


class OfficeApplicationService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        *,
        composition: OfficeComposition | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.composition = composition or build_office_composition(
            settings,
            audit_sink=ProviderAuditRepository(db),
        )
        self.executions = AIExecutionRepository(db)
        self.artifacts = ArtifactRepository(db)

    async def execute_work_package(
        self,
        payload: WorkPackageCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        client_request_id: str | None = None,
    ) -> WorkPackageRecord:
        idempotency_key = client_request_id or payload.client_request_id
        if idempotency_key:
            existing = await self.artifacts.get_package_by_client_request(
                organization_id, idempotency_key
            )
            if existing is not None:
                return existing

        task_record = await self.executions.create_task(
            organization_id=organization_id,
            requesting_user_id=user_id,
            task_type=payload.package_type,
            commit=False,
        )
        task_record.status = "running"
        task = self._task(payload, task_record.id, organization_id, user_id)
        route = self.composition.workflow.plan(task)
        pending_package = OfficeWorkPackage(
            title=payload.package_type.replace("_", " ").title(),
            summary="Work package execution is running.",
            organization_id=organization_id,
            task_id=task_record.id,
            authoring_agent="chief_secretary",
            version="1.0.0",
            review_status=ArtifactReviewStatus.NEEDS_REVIEW,
            package_type=payload.package_type,
        )
        package_record = await self.artifacts.create_package(
            pending_package,
            user_id,
            status="running",
            client_request_id=idempotency_key,
            commit=False,
        )
        runs = {}
        for agent_id in route:
            prompt = self.composition.prompts.get(agent_id, "1.0.0")
            runs[agent_id] = await self.executions.start_run(
                organization_id=organization_id,
                task_id=task_record.id,
                agent_name=agent_id.value,
                prompt_version="1.0.0",
                prompt_hash=prompt.content_hash,
                model_id=self.composition.model_id,
                provider=self.composition.provider,
                commit=False,
            )
        await self.db.commit()

        try:
            outcome = await self.composition.workflow.execute(task)
        except asyncio.CancelledError:
            task_record.status = "cancelled"
            package_record.status = "cancelled"
            for run in runs.values():
                await self.executions.cancel_run(run, commit=False)
            await self.db.commit()
            raise
        except Exception as exc:
            await self.db.rollback()
            task_record.status = "failed"
            package_record.status = "failed"
            for run in runs.values():
                await self.executions.finish_run(
                    run,
                    status="failed",
                    review_status="pending",
                    error_code="provider_unavailable",
                    commit=False,
                )
            await self.db.commit()
            raise OfficeExecutionError(
                "provider_unavailable", "AI provider execution failed", 503
            ) from exc

        result_by_agent = {result.agent_id: result for result in outcome.results}
        for agent_id, run in runs.items():
            result = result_by_agent[agent_id]
            agent = self.composition.registry.get(agent_id)
            failed = result.status is AgentStatus.FAILED
            await self.executions.finish_run(
                run,
                status="failed" if failed else "succeeded",
                review_status="pending",
                result_summary=f"{agent_id.value}: {result.status.value}",
                error_code=result.error.code if result.error else None,
                provider_request_id=getattr(agent, "last_provider_request_id", None),
                usage=result.usage,
                provider_error=getattr(agent, "last_provider_error", None),
                commit=False,
            )

        persisted_agents = {artifact.authoring_agent for artifact in outcome.artifacts}
        artifacts: list[ArtifactMetadata] = list(outcome.artifacts)
        for result in outcome.results:
            if result.status is AgentStatus.FAILED or result.agent_id in persisted_agents:
                continue
            artifacts.append(
                AgentResultArtifact(
                    title=f"{result.agent_id.value.replace('_', ' ').title()} Result",
                    summary="Specialist result requires human review.",
                    organization_id=organization_id,
                    task_id=task_record.id,
                    authoring_agent=result.agent_id,
                    version="1.0.0",
                    review_status=ArtifactReviewStatus.NEEDS_REVIEW,
                    warnings=result.warnings,
                    evidence_references=result.evidence,
                    assumptions=result.assumptions,
                    verified_findings=result.verified_findings,
                    analysis=result.analysis,
                    recommendations=result.recommendations,
                )
            )
        for artifact in artifacts:
            await self.artifacts.create_artifact(
                artifact,
                user_id,
                package_id=package_record.id,
                status="needs_review",
                commit=False,
            )

        failed_results = [
            result for result in outcome.results if result.status is AgentStatus.FAILED
        ]
        total_failure = len(failed_results) == len(outcome.results)
        partial_failure = bool(failed_results) and not total_failure
        final_status = "failed" if total_failure else "needs_review"
        task_record.status = final_status
        package_record.status = final_status
        package_record.review_status = "needs_review"
        package_record.summary = outcome.package.summary
        if partial_failure:
            package_record.summary += " Partial agent failure requires review."
        await self.db.commit()

        if total_failure:
            error_codes = {result.error.code for result in failed_results if result.error}
            code = next(iter(error_codes)) if len(error_codes) == 1 else "provider_unavailable"
            raise self._safe_failure(code)
        return package_record

    @staticmethod
    def _task(
        payload: WorkPackageCreate,
        task_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AgentTask:
        route = WORKFLOW_ROUTES[payload.package_type]
        return AgentTask(
            task_id=task_id,
            user_id=user_id,
            organization_id=organization_id,
            task_type=payload.package_type,
            instruction=payload.instruction,
            allowed_agents=list(route),
            allowed_capabilities=[AGENT_CAPABILITIES[item] for item in route],
            context=AgentContext(data_classification=payload.data_classification),
            status=AgentStatus.RUNNING,
        )

    @staticmethod
    def _safe_failure(code: str) -> OfficeExecutionError:
        if code == "timeout":
            return OfficeExecutionError(code, "AI provider request timed out", 504)
        if code == "provider_policy_blocked":
            return OfficeExecutionError(code, "AI provider transmission blocked", 403)
        if code == "rate_limited":
            return OfficeExecutionError(code, "AI provider is temporarily rate limited", 503)
        if code == "configuration_error":
            return OfficeExecutionError(code, "AI provider is not configured", 503)
        return OfficeExecutionError(code, "AI provider execution failed", 503)
