"""Shared execution mechanics for typed operational agents."""

from typing import ClassVar

from pydantic import ValidationError

from app.ai.artifacts import ArtifactMetadata, ArtifactReviewStatus
from app.ai.domain import (
    AgentIdentifier,
    AgentResult,
    AgentStatus,
    AgentTask,
    StructuredError,
)
from app.ai.model_gateway import ModelGateway, ModelGatewayError, ModelRequest
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
        self.last_artifact: ArtifactMetadata | None = None

    async def execute(self, task: AgentTask) -> AgentResult:
        prompt = self._prompts.get(self.name, self._prompt_version, prompt_name=self.prompt_name)
        request = ModelRequest(
            system_prompt=prompt.content,
            user_instruction=task.instruction,
            structured_context=task.context.model_dump(mode="json"),
            output_schema=self.output_type.model_json_schema(),
            model_id=self._model_id,
        )
        try:
            response = await self._gateway.generate(request)
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
        self.last_artifact = artifact
        return self.to_result(task, artifact, response.usage)

    def _failure(self, task: AgentTask, code: str, message: str, retryable: bool) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.FAILED,
            error=StructuredError(code=code, message=message, retryable=retryable),
        )

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        raise NotImplementedError
