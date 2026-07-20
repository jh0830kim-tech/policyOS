"""Shared execution mechanics for typed operational agents."""

from typing import ClassVar

from pydantic import ValidationError

from app.ai.artifacts import ArtifactMetadata, ArtifactReviewStatus
from app.ai.domain import (
    AgentIdentifier,
    AgentResult,
    AgentStatus,
    AgentTask,
    EvidenceReference,
    StructuredError,
)
from app.ai.model_gateway import ModelGateway, ModelGatewayError, ModelRequest
from app.ai.privacy import ProviderTransmissionContext
from app.ai.prompts import PromptRegistry


class OperationalAgent:
    name: ClassVar[AgentIdentifier]
    version: ClassVar[str] = "1.0.0"
    prompt_name: ClassVar[str] = "system"
    output_type: ClassVar[type[ArtifactMetadata]]

    def __init__(
        self,
        gateway: ModelGateway,
        prompts: PromptRegistry,
        *,
        prompt_version: str,
        model_id: str,
    ) -> None:
        self._gateway = gateway
        self._prompts = prompts
        self._prompt_version = prompt_version
        self._model_id = model_id
        self.last_provider_request_id: str | None = None
        self.last_provider_error: ModelGatewayError | None = None
        self.last_artifact: ArtifactMetadata | None = None

    async def execute(self, task: AgentTask) -> AgentResult:
        prompt = self._prompts.get(self.name, self._prompt_version, prompt_name=self.prompt_name)
        request = ModelRequest(
            system_prompt=prompt.content,
            user_instruction=task.instruction,
            structured_context=task.context.model_dump(mode="json"),
            output_schema=self.output_type.model_json_schema(),
            model_id=self._model_id,
            transmission_context=ProviderTransmissionContext(
                organization_id=task.organization_id,
                authorized_organization_id=task.organization_id,
                user_id=task.user_id,
                task_id=task.task_id,
                data_classification=task.context.data_classification,
            ),
        )
        try:
            response = await self._gateway.generate(request)
            self.last_provider_request_id = response.provider_request_id
            payload = dict(response.structured_output)
            payload.update(
                organization_id=task.organization_id,
                task_id=task.task_id,
                authoring_agent=self.name,
                version=self.version,
                review_status=ArtifactReviewStatus.NEEDS_REVIEW,
                approval_required=True,
            )
            artifact = self.output_type.model_validate(payload)
        except ModelGatewayError as exc:
            return self._failure(task, exc.code.value, exc.safe_message, exc.retryable)
        except ValidationError:
            return self._failure(
                task,
                "invalid_model_output",
                "Model output did not match the artifact schema",
                False,
            )
        evidence_package = task.context.knowledge_evidence
        evidence_references = []
        if evidence_package is not None:
            evidence_references = [
                EvidenceReference(
                    evidence_id=item.evidence_id,
                    title=item.source_title,
                    source_type=item.source_type,
                    locator=item.citation or "citation unavailable",
                    excerpt=item.excerpt,
                    retrieved_at=item.retrieved_at,
                )
                for item in evidence_package.evidence_items
            ]
            artifact = artifact.model_copy(
                update={
                    "evidence_references": evidence_references,
                    "warnings": list(
                        dict.fromkeys([*artifact.warnings, *evidence_package.warnings])
                    ),
                    "review_status": ArtifactReviewStatus.NEEDS_REVIEW,
                    "approval_required": True,
                }
            )
        self.last_artifact = artifact
        result = self.to_result(task, artifact, response.usage)
        if evidence_package is not None:
            result = result.model_copy(
                update={
                    "evidence": evidence_references,
                    "evidence_ids_used": [
                        item.evidence_id for item in evidence_package.evidence_items
                    ],
                    "citation_ids_used": list(evidence_package.citations),
                    "evidence_conflicts": [str(item) for item in evidence_package.conflicts],
                    "evidence_gaps": [str(item) for item in evidence_package.gaps],
                    "stale_source_warnings": [
                        warning
                        for item in evidence_package.evidence_items
                        if item.freshness == "stale"
                        for warning in item.warnings or ("stale source",)
                    ],
                    "effective_date_used": (
                        evidence_package.effective_date_context.isoformat()
                        if evidence_package.effective_date_context
                        else None
                    ),
                    "fiscal_year_used": evidence_package.fiscal_year_context,
                    "review_notes": list(evidence_package.warnings),
                    "requires_human_review": evidence_package.requires_human_review,
                }
            )
        return result

    def _failure(self, task: AgentTask, code: str, message: str, retryable: bool) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.FAILED,
            error=StructuredError(code=code, message=message, retryable=retryable),
        )

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        raise NotImplementedError
